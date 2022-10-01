from libabaev2 import *
import re
import os

langdata = LanguageDict.from_csv("../abaev-tei-oxygen/css/langnames.csv")
entries = EntryDict()
forms = FormDict()
senses = SenseDict()
sense_groups = SenseGroupDict()
examples = ExampleDict()
example_groups = ExampleGroupDict()
mentioneds = MentionedDict()
directory = "../abaevdict-tei/entries"
for file in os.listdir(directory):
    if file.endswith(".xml") and \
            not(file.startswith("abaev_!")) and \
            re.match(r'abaev_[78]?[AaÆæBbCcDdƷʒEeFfGgǴǵǦǧIiĪīJjKkḰḱLlMmNnOoPpQqRr]', file):
        entry_file = open(os.path.join(directory, file), "r")
        tree = etree.parse(entry_file)
        entry_file.close()

        node = tree.xpath("//tei:entry", namespaces=NAMESPACES)[0]

        n_entries, n_forms, n_sense_groups, n_senses, n_example_groups, n_examples, n_mentioneds = \
            get_dict_info(node=node)

        entries = entries | n_entries
        forms = forms | n_forms
        senses = senses | n_senses
        sense_groups = sense_groups | n_sense_groups
        examples = examples | n_examples
        example_groups = example_groups | n_example_groups
        mentioneds = mentioneds | n_mentioneds


# sorted_keys = sorted(entries, key=abaev_key)
# sorted_entries = {key: entries[key] for key in sorted_keys}

with open("entries.csv", "w") as file:
    serialize_dict(entries, file)
with open("forms.csv", "w") as file:
    serialize_dict(forms, file)
with open("senses.csv", "w") as file:
    serialize_dict(senses, file)
with open("senseGroups.csv", "w") as file:
    serialize_dict(sense_groups, file)
with open("examples.csv", "w") as file:
    serialize_dict(examples, file)
with open("exampleGroups.csv", "w") as file:
    serialize_dict(example_groups, file)
with open("mentioneds.csv", "w") as file:
    serialize_dict(mentioneds, file)