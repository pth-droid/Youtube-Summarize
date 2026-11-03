# Fonts

`bricolage-grotesque.woff2` is **Bricolage Grotesque** by Atelier Triay, version 1.001.

Copyright 2022 The Bricolage Grotesque Project Authors (https://github.com/ateliertriay/bricolage). It is licensed under the [SIL Open Font License, Version 1.1](https://openfontlicense.org). The file keeps the font's own copyright and license fields.

The maroon deck look uses it for titles and text. Decks in that look carry it inside the file, so a phone or a computer without the font shows the same type. The app serves it for its look pickers.

It was made from the variable font `BricolageGrotesque-VariableFont_opsz,wdth,wght.ttf` with fontTools 4.68:

- **Width** is fixed at normal (`wdth` 100), with `varLib.instancer`.
- **Weight** (200–800) and **optical size** (12–96) stay variable.
- **Characters** are subset with `pyftsubset` to Latin and Vietnamese: Google Fonts' latin and vietnamese ranges, plus arrows. The command keeps every OpenType feature and name record (`--layout-features=* --name-IDs=* --flavor=woff2`).

## Be Vietnam Pro

`be-vietnam-pro-regular.woff`, `-medium.woff`, `-semibold.woff` and `-bold.woff` are **Be Vietnam Pro** by Lam Bao, Tony Le and Vietanh Nguyen (Yellow Type Foundry), version 1.002. The workspace sets all its text in it.

Copyright 2021 The Be Vietnam Pro Project Authors (https://github.com/bettergui/BeVietnamPro). It is licensed under the [SIL Open Font License, Version 1.1](https://openfontlicense.org). The files keep the font's own copyright and license fields.

They were made from the installed static fonts (`BeVietnamPro-Regular.ttf` and the others) with fontTools 4.62, subset with `pyftsubset` to the same Latin and Vietnamese ranges as above plus arrows (`--layout-features=* --name-IDs=* --flavor=woff`). They are WOFF rather than WOFF2 because that fontTools had no Brotli module.
