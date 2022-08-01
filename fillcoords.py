# This script fills in the missing coordinates of languages in langnames.csv from Glottolog
# Usage: fill-coords langnames.csv
# Output: comma-separated CSV to stdout

import csv
import sys
from pyglottolog import Glottolog
import libabaev

filename = sys.argv[1]

# Open the langnames.csv from 
langdata = libabaev.AbaevLangDict.from_csv(filename)

glottolog = Glottolog('./glottolog')
for key in langdata:
    lang = langdata[key]
    if not lang.latitude:
        languoid = glottolog.languoid(lang.glottocode)
        if languoid:
            lang.latitude = languoid.latitude
            lang.longitude = languoid.longitude

langdata.write_csv(sys.stdout)