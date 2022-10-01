from __future__ import annotations
from typing import *
from libabaev2 import *
import folium
import sys

entryname = sys.argv[1]

langs = LanguageDict.from_csv("../abaev-tei-oxygen/css/langnames.csv")
entries = get_entries_from_csv("csv/entries.csv")
forms = get_forms_from_csv("csv/forms.csv")
senses = get_senses_from_csv("csv/senses.csv")
sense_groups = get_sense_groups_from_csv("csv/senseGroups.csv")
examples = get_examples_from_csv("csv/examples.csv")
example_groups = get_example_groups_from_csv("csv/exampleGroups.csv")
mentioneds = get_mentioneds_from_csv("csv/mentioneds.csv")

def plot_mentioneds(entry_id: str, ments: MentionedDict):
    m = folium.Map(tiles="Stamen Terrain",location=[42.98,44.61],zoom_start=4)
    folium.Marker(location=[42.98,44.61],icon=folium.Icon(color='red')).add_to(m)
    for key in ments:
        if ments[key]["entry_id"] == entry_id:
            ment_langs = ments[key]["langs"]
            gloss = ments[key]["gloss_en"]
            if gloss: gloss = "‘" + gloss[0] + "’"
            else: gloss = ''
            for lang in ment_langs:
                if lang in langs.keys():
                    if langs[lang]["latitude"] != -99 and not(lang == "os" or lang.startswith("os-")):
                        folium.Marker(location=[langs[lang]["latitude"],langs[lang]["longitude"]],
                        tooltip=folium.Tooltip(text=ments[key]["form"][0],permanent=True),
                        popup=folium.Popup(html=langs[lang]["name_en"] + " <i>" + ments[key]["form"][0] + "</i> " + gloss,
                            show=False)).add_to(m)
    return m

plot_mentioneds("entry_" + entryname,mentioneds).save("map.html")