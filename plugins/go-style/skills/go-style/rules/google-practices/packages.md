# Google Go Style Best Practices — Packages and imports

How large packages and files should be, how to name protocol buffer imports, and how to order
imports.

### google-practices:package-size — Package and file size
- **meta:** severity=consider · scope=repo · check=lint+llm · lint=revive:file-length-limit
- **rule:** Keep types whose implementation is tightly coupled, or that clients need together, in
  one package (if users must import both packages to use either, merge them); give conceptually
  distinct things their own small package, so package and type names form a meaningful identifier
  (`bytes.Buffer`), rather than putting a whole project in one package. Files have no fixed size
  and no "one type per file" rule, but avoid files of many thousands of lines and many tiny files:
  a maintainer should be able to tell which file holds something. A `doc.go` is optional.
- **look for:** packages always imported together, or exporting identifiers only for each other;
  catch-all packages mixing unrelated domains; files thousands of lines long; a package split
  into many tiny one-type files.
- **skip:** files over the configured length — revive reports them; Bazel layouts with several
  `go_library` targets in one directory.

### google-practices:import-protos — Naming protocol buffer and gRPC imports
- **meta:** severity=should · scope=decl · check=llm · custom=proto-import-alias · overlaps=google-decisions:import-renaming
- **rule:** Rename generated proto imports by the rule that generated them: suffix `pb` for
  `go_proto_library`, `grpc` for `go_grpc_library` (`foopb`, `foogrpc`). The local name follows
  package-name style: prefer whole, descriptive words and avoid ambiguity; when in doubt, use the
  proto package name up to `_go` plus `pb` (`pushqueueservicepb`). Very short names (`pb`, `xpb`)
  from older guidance should not be copied, but existing ones need not change.
- **look for:** `_go_proto`/`_go_grpc` imports with no alias or an alias without the suffix;
  underscored aliases (`foo_pb`); new cryptic aliases (`pb`, `xpb`, `fpb`).
- **skip:** existing short aliases in lines the change does not touch.
- **note:** the convention is stated for Bazel rules; outside Bazel, report only clear cases
  (generated packages imported under underscored or cryptic names).
- **example:** `pb "path/to/push_queue_service_go_proto"` -> `pushqueueservicepb "path/to/push_queue_service_go_proto"`

### google-practices:import-order — Import ordering
- **meta:** severity=should · scope=decl · check=lint+llm · lint=goimports · custom=import-groups · overlaps=google-decisions:import-grouping · conflicts=uber:import-group-ordering
- **rule:** Defers to Go Style Decisions: imports form blank-line-separated groups in this order —
  standard library, other (project and vendored) packages, protocol buffer imports, then imports
  for side effects (`_`).
- **look for:** proto imports (`...pb`, `_go_proto`) mixed into the other-packages group; `_`
  imports outside a final group of their own; a standard-library group placed after another group.
- **skip:** standard-library imports mixed with others in one group, unsorted groups — goimports
  reports them.
