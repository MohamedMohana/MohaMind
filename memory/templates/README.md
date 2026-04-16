# Memory templates

These are the **structural scaffolds** MohaMind uses to seed an empty
`memory/` directory on first run. They contain only section headers and
HTML-comment hints — no personal data.

If a given `memory/<category>.md` file does not exist when MohaMind starts,
the corresponding template from this folder is copied into place so you can
immediately see the expected structure. After that, MohaMind (and you) are
free to edit the real file — which stays local and gitignored.

To customize the scaffolding for your own fork, edit the files in this
directory. To reset a category to the template, delete
`memory/<category>.md` and restart MohaMind.
