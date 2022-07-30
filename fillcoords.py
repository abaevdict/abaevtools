# This script fills in the missing coordinates of languages in langnames.csv from Glottolog
# Usage: fill-coords langnames.csv
# Output: comma-separated CSV to stdout

import csv
import sys
from pyglottolog import Glottolog

langdata = {}
filename = sys.argv[1]

# Open the langnames.csv from 
with open(filename) as csv_file:
    csv_reader = csv.DictReader(csv_file, delimiter=',')
    for row in csv_reader:
        code = row.pop("code")
        langdata[code] = row

glottolog = Glottolog('./glottolog')
for key in langdata:
    lang = langdata[key]
    if not lang["lat"]:
        languoid = glottolog.languoid(lang["glottolog"])
        if languoid:
            lang["lat"] = languoid.latitude
            lang["long"] = languoid.longitude

with sys.stdout as csv_file:
    csv_writer = csv.DictWriter(csv_file, fieldnames=['code'] + list(langdata[list(langdata)[0]].keys()), delimiter=',')
    for key in sorted(langdata.keys()):
        csv_writer.writerow({"code" : key} | langdata[key])
