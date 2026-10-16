// Command outline prints a compact declaration outline of Go source files: the
// package clause and package comment, the imports, and one line per top-level
// declaration with its line number, its signature and the first sentence of its
// doc comment.
//
// The outline lets a reviewer check names, doc comments and API shape across a
// whole module without reading every function body. It uses only the standard
// library, so `go run outline.go` works in any environment that has Go.
//
// Usage:
//
//	go run outline.go -root DIR < paths.txt
//
// Each input line is a file path relative to DIR. Files are grouped by
// directory in the output.
package main

import (
	"bufio"
	"flag"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"go/types"
	"io"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"unicode"
	"unicode/utf8"
)

// Limits that keep one declaration on one readable line.
const (
	maxDocLen  = 120
	maxExprLen = 60
)

func main() {
	root := flag.String("root", ".", "directory the input paths are relative to")
	members := flag.Int("members", 8,
		"struct fields and interface methods to show per type")
	flag.Parse()

	if err := run(os.Stdin, os.Stdout, *root, *members); err != nil {
		fmt.Fprintf(os.Stderr, "outline: %v\n", err)
		os.Exit(1)
	}
}

func run(in io.Reader, out io.Writer, root string, members int) error {
	paths, err := readPaths(in)
	if err != nil {
		return err
	}
	w := bufio.NewWriter(out)
	p := &printer{w: w, members: members}
	for _, dir := range groupByDir(paths) {
		p.pkg(root, dir.name, dir.files)
	}
	return w.Flush()
}

func readPaths(r io.Reader) ([]string, error) {
	var paths []string
	sc := bufio.NewScanner(r)
	for sc.Scan() {
		if line := strings.TrimSpace(sc.Text()); line != "" {
			paths = append(paths, filepath.ToSlash(line))
		}
	}
	if err := sc.Err(); err != nil {
		return nil, fmt.Errorf("reading paths: %w", err)
	}
	return paths, nil
}

type dirFiles struct {
	name  string
	files []string
}

func groupByDir(paths []string) []dirFiles {
	byDir := make(map[string][]string)
	for _, p := range paths {
		d := filepath.ToSlash(filepath.Dir(p))
		byDir[d] = append(byDir[d], p)
	}
	dirs := make([]dirFiles, 0, len(byDir))
	for d, files := range byDir {
		slices.Sort(files)
		dirs = append(dirs, dirFiles{name: d, files: files})
	}
	slices.SortFunc(dirs, func(a, b dirFiles) int {
		return strings.Compare(a.name, b.name)
	})
	return dirs
}

// printer writes the outline. It keeps going after a write error and lets the
// final Flush report it.
type printer struct {
	w       *bufio.Writer
	members int
}

func (p *printer) printf(format string, args ...any) {
	fmt.Fprintf(p.w, format, args...)
}

type parsedFile struct {
	path  string
	file  *ast.File
	lines int
	err   error
}

func (p *printer) pkg(root, dir string, paths []string) {
	fset := token.NewFileSet()
	var files []parsedFile
	total := 0
	for _, path := range paths {
		f, err := parser.ParseFile(fset, filepath.Join(root, path), nil,
			parser.ParseComments|parser.SkipObjectResolution)
		pf := parsedFile{path: path, file: f, err: err}
		if f != nil {
			pf.lines = fset.File(f.Pos()).LineCount()
			total += pf.lines
		}
		files = append(files, pf)
	}

	p.printf("== %s · package %s · %s · %s\n", dir, packageNames(files),
		plural(len(files), "file"), plural(total, "line"))
	docs := 0
	for _, pf := range files {
		if pf.file != nil && pf.file.Doc != nil {
			docs++
			p.printf("pkgdoc %s:%d: %s\n", filepath.Base(pf.path),
				fset.Position(pf.file.Doc.Pos()).Line, docText(pf.file.Doc))
		}
	}
	if docs == 0 {
		p.printf("pkgdoc: none\n")
	}
	for _, pf := range files {
		p.file(fset, pf)
	}
	p.printf("\n")
}

// packageNames lists the distinct package names of a directory, so that an
// external test package shows up next to the package under test.
func packageNames(files []parsedFile) string {
	seen := make(map[string]bool)
	var names []string
	for _, pf := range files {
		if pf.file == nil || seen[pf.file.Name.Name] {
			continue
		}
		seen[pf.file.Name.Name] = true
		names = append(names, pf.file.Name.Name)
	}
	return strings.Join(names, ", ")
}

func (p *printer) file(fset *token.FileSet, pf parsedFile) {
	if pf.file == nil {
		p.printf("-- %s · parse error: %v\n", pf.path, pf.err)
		return
	}
	p.printf("-- %s · %s\n", pf.path, plural(pf.lines, "line"))
	if imps := imports(fset, pf.file); imps != "" {
		p.printf("imports: %s\n", imps)
	}
	for _, decl := range pf.file.Decls {
		switch d := decl.(type) {
		case *ast.FuncDecl:
			p.funcDecl(fset, d)
		case *ast.GenDecl:
			p.genDecl(fset, d)
		}
	}
}

// imports renders the import specs in source order; " | " separates groups
// (specs separated by a blank line).
func imports(fset *token.FileSet, f *ast.File) string {
	var b strings.Builder
	prevEnd := 0
	for i, imp := range f.Imports {
		start := fset.Position(imp.Pos()).Line
		switch {
		case i == 0:
		case start > prevEnd+1:
			b.WriteString(" | ")
		default:
			b.WriteString(", ")
		}
		if imp.Name != nil {
			fmt.Fprintf(&b, "%s ", imp.Name.Name)
		}
		b.WriteString(imp.Path.Value)
		prevEnd = fset.Position(imp.End()).Line
	}
	return b.String()
}

func (p *printer) funcDecl(fset *token.FileSet, d *ast.FuncDecl) {
	var b strings.Builder
	b.WriteString("func ")
	if d.Recv != nil {
		fmt.Fprintf(&b, "%s ", fieldList(d.Recv, false))
	}
	fmt.Fprintf(&b, "%s%s%s", d.Name.Name, typeParams(d.Type.TypeParams),
		fieldList(d.Type.Params, false))
	if res := fieldList(d.Type.Results, true); res != "" {
		fmt.Fprintf(&b, " %s", res)
	}
	start := fset.Position(d.Pos()).Line
	if d.Body != nil {
		fmt.Fprintf(&b, " [%s]", plural(fset.Position(d.Body.End()).Line-start+1, "line"))
	}
	exported := isExported(d.Name.Name)
	if d.Recv != nil && len(d.Recv.List) > 0 {
		exported = exported && isExported(receiverType(d.Recv.List[0].Type))
	}
	p.line(start, b.String(), d.Doc, exported)
}

// receiverType returns the base type name of a receiver: T for T, *T, T[K]
// and *T[K].
func receiverType(e ast.Expr) string {
	for {
		switch t := e.(type) {
		case *ast.StarExpr:
			e = t.X
		case *ast.IndexExpr:
			e = t.X
		case *ast.IndexListExpr:
			e = t.X
		case *ast.Ident:
			return t.Name
		default:
			return ""
		}
	}
}

// genDecl prints type, const and var declarations. A parenthesized group gets
// a header line carrying the group's doc comment, and its specs are indented;
// a spec inside a documented group is not marked as undocumented.
func (p *printer) genDecl(fset *token.FileSet, d *ast.GenDecl) {
	if d.Tok == token.IMPORT {
		return
	}
	grouped := d.Lparen.IsValid()
	prefix := d.Tok.String() + " "
	if grouped {
		header := fmt.Sprintf("%s (", d.Tok)
		if text := docText(d.Doc); text != "" {
			header += " // " + text
		}
		p.printf("%d %s\n", fset.Position(d.Pos()).Line, header)
		prefix = "  "
	}
	for _, spec := range d.Specs {
		var (
			pos  token.Pos
			text string
			name string
			doc  *ast.CommentGroup
		)
		switch s := spec.(type) {
		case *ast.TypeSpec:
			pos, name, doc = s.Pos(), s.Name.Name, s.Doc
			text = prefix + p.typeSpec(s)
		case *ast.ValueSpec:
			pos, name, doc = s.Pos(), s.Names[0].Name, s.Doc
			text = prefix + valueSpec(s)
		default:
			continue
		}
		if !grouped && doc == nil {
			doc = d.Doc
		}
		exported := isExported(name) && !(grouped && d.Doc != nil)
		p.line(fset.Position(pos).Line, text, doc, exported)
	}
}

func (p *printer) typeSpec(s *ast.TypeSpec) string {
	var b strings.Builder
	fmt.Fprintf(&b, "%s%s", s.Name.Name, typeParams(s.TypeParams))
	if s.Assign.IsValid() {
		b.WriteString(" =")
	}
	switch t := s.Type.(type) {
	case *ast.StructType:
		fmt.Fprintf(&b, " struct {%s}", p.memberList(t.Fields, structField))
	case *ast.InterfaceType:
		fmt.Fprintf(&b, " interface {%s}", p.memberList(t.Methods, ifaceMethod))
	default:
		fmt.Fprintf(&b, " %s", expr(s.Type))
	}
	return b.String()
}

// typeParams renders a type parameter list such as [K comparable, V any].
func typeParams(fl *ast.FieldList) string {
	if fl == nil {
		return ""
	}
	return "[" + strings.Trim(fieldList(fl, false), "()") + "]"
}

// memberList renders up to p.members entries of a struct or interface body.
func (p *printer) memberList(fl *ast.FieldList, render func(*ast.Field) string) string {
	if fl == nil || len(fl.List) == 0 {
		return ""
	}
	var parts []string
	for i, f := range fl.List {
		if i == p.members {
			parts = append(parts, fmt.Sprintf("… +%d", len(fl.List)-i))
			break
		}
		parts = append(parts, render(f))
	}
	return strings.Join(parts, "; ")
}

func structField(f *ast.Field) string {
	if len(f.Names) == 0 {
		return "embedded " + expr(f.Type)
	}
	return joinNames(f.Names) + " " + expr(f.Type)
}

func ifaceMethod(f *ast.Field) string {
	ft, ok := f.Type.(*ast.FuncType)
	if !ok || len(f.Names) == 0 {
		return expr(f.Type) // embedded interface or type constraint
	}
	s := f.Names[0].Name + fieldList(ft.Params, false)
	if res := fieldList(ft.Results, true); res != "" {
		s += " " + res
	}
	return s
}

func valueSpec(s *ast.ValueSpec) string {
	var b strings.Builder
	b.WriteString(joinNames(s.Names))
	if s.Type != nil {
		fmt.Fprintf(&b, " %s", expr(s.Type))
	}
	if len(s.Values) > 0 {
		vals := make([]string, len(s.Values))
		for i, v := range s.Values {
			vals[i] = expr(v)
		}
		fmt.Fprintf(&b, " = %s", strings.Join(vals, ", "))
	}
	return b.String()
}

// line prints one declaration. An exported declaration without a doc comment
// is marked, because that is what documentation rules look for first.
func (p *printer) line(n int, text string, doc *ast.CommentGroup, exported bool) {
	switch d := docText(doc); {
	case d != "":
		p.printf("%d %s // %s\n", n, text, d)
	case exported:
		p.printf("%d %s // (no doc)\n", n, text)
	default:
		p.printf("%d %s\n", n, text)
	}
}

func isExported(name string) bool {
	r, _ := utf8.DecodeRuneInString(name)
	return unicode.IsUpper(r)
}

// fieldList renders a parameter, result, receiver or type parameter list. For
// results, a single unnamed type is printed without parentheses.
func fieldList(fl *ast.FieldList, results bool) string {
	if fl == nil || len(fl.List) == 0 {
		if results {
			return ""
		}
		return "()"
	}
	parts := make([]string, 0, len(fl.List))
	for _, f := range fl.List {
		if len(f.Names) == 0 {
			parts = append(parts, expr(f.Type))
			continue
		}
		parts = append(parts, joinNames(f.Names)+" "+expr(f.Type))
	}
	s := strings.Join(parts, ", ")
	if results && len(fl.List) == 1 && len(fl.List[0].Names) == 0 {
		return s
	}
	return "(" + s + ")"
}

func joinNames(ids []*ast.Ident) string {
	names := make([]string, len(ids))
	for i, id := range ids {
		names[i] = id.Name
	}
	return strings.Join(names, ", ")
}

func expr(e ast.Expr) string {
	return truncate(types.ExprString(e), maxExprLen)
}

// docText returns the first sentence of a doc comment, or "" when there is
// no comment or it holds only directives such as //go:embed.
func docText(cg *ast.CommentGroup) string {
	if cg == nil {
		return ""
	}
	text := strings.Join(strings.Fields(cg.Text()), " ")
	if i := strings.Index(text, ". "); i >= 0 {
		text = text[:i+1]
	}
	return truncate(text, maxDocLen)
}

func plural(n int, word string) string {
	if n == 1 {
		return "1 " + word
	}
	return fmt.Sprintf("%d %ss", n, word)
}

func truncate(s string, n int) string {
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n-1]) + "…"
}
