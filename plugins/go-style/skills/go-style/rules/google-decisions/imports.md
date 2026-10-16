# Google Style Decisions — Imports

Imports: when and how to rename them, how to group them, and the limits on blank (`_`) and
dot (`.`) imports.

### google-decisions:import-renaming/local-name — Import renaming: valid, consistent local names
- **meta:** severity=must · scope=decl · check=lint+llm · lint=revive:import-alias-naming · custom=import-name-underscore
- **rule:** A package's local name must follow the package-name rules (lowercase, no
  underscores or capitals), so a package whose name has underscores must be renamed on import;
  generated protobuf packages are renamed with a `pb` suffix (`foosvcpb`). A name collision
  must be resolved by renaming, preferably the most local or project-specific import. Use the
  same local name for the same package everywhere, especially in nearby packages.
- **look for:** unrenamed imports of packages with underscores (`foo_service_go_proto`); proto
  imports without a `pb` suffix; one package imported under different names across files;
  collisions solved by renaming the standard or widely used import instead of the local one.
- **skip:** aliases with capitals or underscores — revive reports them.
- **example:** `import "path/to/foo_service_go_proto"` -> `import foosvcpb "path/to/foo_service_go_proto"`

### google-decisions:import-renaming/unnecessary — Import renaming: only when it helps
- **meta:** severity=should · scope=decl · check=lint+llm · lint=revive:redundant-import-alias · conflicts=uber:import-aliasing
- **rule:** Imports should not normally be renamed; a good package name needs no rename. A
  non-generated package with an uninformative name (`util`, `v1`) may be renamed, sparingly,
  when the surrounding code gives too little context — better, rename the package itself. To
  keep a common local variable name (`url`, `ssh`) while the package is still needed in that
  scope, rename the import with a `pkg` suffix (`urlpkg`).
- **look for:** aliases that only shorten or restyle a well-named package (`str "strings"`);
  renames made to free a variable name that skip the `pkg` suffix (`u "net/url"`, `neturl`) or
  are not needed because the package is unused where the variable lives.
- **skip:** aliases equal to the package name (revive reports them); renames the local-name
  rule requires.

### google-decisions:import-grouping — Import grouping
- **meta:** severity=should · scope=decl · check=lint+llm · lint=goimports · custom=import-group-order · conflicts=uber:import-group-ordering
- **rule:** Organize imports into these groups, in order, separated by blank lines: standard
  library; other (project and vendored) packages; protocol buffer imports
  (`foopb "path/to/foo_go_proto"`); side-effect imports (`_ "path/to/package"`).
- **look for:** proto imports mixed into the general group; blank `_` imports outside a final
  group of their own; the standard-library group not first.
- **skip:** standard-library and other imports run together in one block (goimports reports it).
- **example:** `_ "myproj/rpc/dial"` among regular imports -> moved into a last, separate group

### google-decisions:import-blank — Import "blank" (import _)
- **meta:** severity=must · scope=decl · check=lint+llm · lint=revive:blank-imports
- **rule:** Side-effect imports (`import _ "pkg"`) belong only in `main` packages or in tests
  that need them; keep them out of libraries even when the library indirectly depends on them,
  so dependencies stay controllable and tests can pick a different import. The only exceptions:
  a blank import to bypass the nogo disallowed-import check, and `_ "embed"` in a file using
  `//go:embed`. A library that needs a side-effect import in production should document it.
- **look for:** blank imports in non-main, non-test packages that carry a justifying comment —
  revive accepts any comment, the guide does not (`_ "image/png" // decoder` in a library).
- **skip:** uncommented blank imports in libraries (revive reports them); `main` packages and
  `_test.go` files; `_ "embed"` next to `//go:embed`.

### google-decisions:import-dot — Import "dot" (import .)
- **meta:** severity=must · scope=decl · check=lint · lint=revive:dot-imports
- **rule:** Do not use `import .`, including in `_test` packages that import the package under
  test: unqualified identifiers hide which package they come from.
- **example:** `import . "foo"` … `Bar()` -> `import "foo"` … `foo.Bar()`
