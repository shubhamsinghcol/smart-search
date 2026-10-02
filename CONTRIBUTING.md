# Contributing to Smart:Search

Report reproducible problems through GitHub Issues. Include your Anki version, operating system, search query, and expected behavior. Avoid sharing private collection contents.

## Source and releases

The downloadable release is newer than the source currently published in this repository. The current build script and expanded tests are in the development checkout; publishing that source is pending. Install the release `.ankiaddon`, not the automatically generated source ZIP.

## Current development checkout

```sh
python3 -m unittest discover -s tests
python3 scripts/build_addon.py
```

The builder creates `release/Smart-Search-Windows-AppleSilicon.ankiaddon` and a separate semantic-model ZIP. Runtime dependencies must already be prepared before packaging. Private collection caches, cards, and notes must never be included.

## Verification

Windows support is new and has not yet been verified in a live Windows Anki installation. Packaged semantic runtimes target Python 3.13, Windows x64, and Apple Silicon macOS 14 or later. Automated tests do not establish live runtime behavior or measured retrieval accuracy.

## Licensing

No open-source license has been granted for the author's original code. Third-party resources retain their own terms; see [CREDITS.md](CREDITS.md).
