# IBM maintenance semantics

This project must not infer an installation path from version ordering alone.

## Rules

- **Db2 mod/fix packs**: may be treated as cumulative only when IBM documentation for the release says so.
- **Db2 cumulative special builds (CSB)**: tracked as a maintenance level in addition to `V.R.M.F`; do not reduce `11.5.9.0 special_63280` to `11.5.9.0`.
- **WebSphere fix packs**: cumulative, but installed interim fixes must be re-evaluated for applicability after a fix-pack update.
- **Interim fixes / hotfixes**: default semantics are `unknown`. A provider must capture IBM-declared prerequisites, co-requisites and supersedence. The planner must not assume that the numerically newest fix replaces all older fixes.
- **ICN interim fixes**: mark as cumulative only when the readme for that exact release/fix explicitly states that previous interim fixes are included.

The online checker will therefore build an applicability/dependency graph before producing an installation plan.
