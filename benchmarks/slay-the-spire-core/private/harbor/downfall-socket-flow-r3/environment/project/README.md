# Pinned Downfall source build

Source revision: 030ff7d4a7419a3e21c3075661550b1b479f3502.
Run `bash build.sh` from this project. It builds all Java source offline on JDK 8.
Public artwork/localization is provided separately under `/opt/sts/downfall-resources`.
Licensed game and public SDK dependencies are under `/opt/sts/lib`.
`compile-only` contains signatures for optional integrations absent from this runtime;
those classes are excluded from the generated mod. The unused optional JFR import
is omitted for JDK 8. No executable source statement was changed during preparation.
