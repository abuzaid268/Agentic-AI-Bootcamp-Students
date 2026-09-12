#!/bin/bash
# Builds a throwaway messy folder for the file-organizer demo (Part 1, demo 1).
# Use this instead of your real ~/Downloads: nothing personal on the projector,
# and you can reset it between the rehearsal and the live run.
#
#   ./make-messy-folder.sh            -> ~/m5b-messy
#   ./make-messy-folder.sh /tmp/foo   -> /tmp/foo
set -e
DIR="${1:-$HOME/m5b-messy}"
rm -rf "$DIR"; mkdir -p "$DIR"
cd "$DIR"

# invoices and receipts, inconsistently named, several months
for m in 01 02 03 04; do
  printf 'INVOICE 2026-%s-14\nVendor: Acme\nTotal: $%d.00\n' "$m" $((m*137)) > "invoice_2026${m}.pdf"
done
printf 'RECEIPT\nCoffee\n$4.20\n' > "scan (3).pdf"
printf 'RECEIPT\nCoffee\n$4.20\n' > "scan (3) copy.pdf"      # exact duplicate
printf 'RECEIPT\nTaxi\n$31.00\n' > "Scanned Document 7.pdf"

# camera dumps with duplicates
for n in 4471 4472 4473 4474 4475; do
  printf 'JPEGDATA-%s\n' "$n" > "IMG_${n}.jpg"
done
cp IMG_4471.jpg "IMG_4471 (1).jpg"                           # exact duplicate
cp IMG_4472.jpg "IMG_4472 copy.jpg"                          # exact duplicate

# the same deck, five times, which is the real-world case
for v in v1 v2 v2-FINAL final FINAL-final-USE-THIS; do
  printf 'slide deck %s\n' "$v" > "Q3 review ${v}.pptx"
done

# downloads nobody ever opened again
printf 'zip\n'  > "archive(2).zip"
printf 'dmg\n'  > "Setup-1.4.2.dmg"
printf 'csv\n'  > "export (final).csv"
printf 'csv\n'  > "export (final) (1).csv"                   # exact duplicate
printf 'log\n'  > "untitled.txt"
printf 'log\n'  > "untitled 2.txt"
printf 'notes\n'> "asdfasdf.md"

# a couple of big-ish files so `du -sh` has something to say
mkdir -p "old stuff"
head -c 2000000 /dev/urandom > "old stuff/backup.bin"
head -c 2000000 /dev/urandom > "bigfile.bin"

echo "Built $(find "$DIR" -type f | wc -l | tr -d ' ') files in $DIR"
du -sh "$DIR"
