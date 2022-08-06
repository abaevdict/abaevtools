from __future__ import annotations
import os
import csv
import sys
from dataclasses import dataclass
from enum import Enum,auto
from lxml import etree
from typing import *

NAMESPACES = {"tei": "http://www.tei-c.org/ns/1.0", "abv":"http://ossetic-studies.org/ns/abaevdict"}

def normalize(string: str) -> str:
    return " ".join(string.split())

class Language(TypedDict):
    code: str
    glottocode: str
    name_ru: str
    name_en: str
    comment: str
    latitude: float
    longitude: float

class LanguageDict(Dict[str,Language]):
    @classmethod
    def from_csv(cls,filename: str):
        dict = cls()
        with open(filename) as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=',')
            for row in csv_reader:
                code = row["code"]
                dict[code] = Language()
                dict[code]["code"] = code
                dict[code]["glottocode"] = row["glottolog"]
                dict[code]["name_ru"] = row["ru"]
                dict[code]["name_en"] = row["en"]
                dict[code]["comment"] = row["comment"]
                dict[code]["latitude"] = row["lat"]
                dict[code]["longitude"] = row["long"]
        return dict

    def write_csv(self, file):
        with file as csv_file:
            fieldnames = list(list(self.values())[1].asdict().keys())
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=',')
            csv_writer.writeheader()
            for key in sorted(self.keys()):
                row = {}
                row["code"] = key
                row["glottolog"] = self[key]["glottocode"]
                row["ru"] = self[key]["name_ru"]
                row["en"] = self[key]["name_en"]
                row["comment"] = self[key]["comment"]
                row["lat"] = self[key]["latitude"]
                row["long"] = self[key]["longitude"]
                csv_writer.writerow(row)

class Entry(TypedDict):
    db_id: str # Equivalent to the XML id
    lemma: str
    lang: str # Language ID
    num: int = None

def get_entry(node: lxml.etree._Element) -> Entry:
    entry = Entry()
    entry["db_id"] = node.xpath("@xml:id",namespaces = NAMESPACES)[0]
    entry["lemma"] = node.xpath("string(tei:form[@type='lemma']/tei:orth)", namespaces = NAMESPACES)
    entry["lang"] = node.xpath("@xml:lang",namespaces = NAMESPACES)[0]
    num = None
    num_node = node.xpath("@n", namespaces = NAMESPACES)
    if len(num_node) > 0:
        num = num_node[0]
    entry["num"] = num
    return entry

EntryDict = dict[str,Entry]

class FormRelType(Enum):
    VARIANT = "variant"
    PARTICIPLE = "participle"

class Form(TypedDict):
    db_id: str # Should be same as XML id because forms are never unified
    entry_id: str # ID of the entry to which the form belongs
    orth: str
    lang: str # Language ID
    rel_of: str = None # If variant or participle of something, ID here
    rel_type: FormRelType = None # Type of variant or participle

FormDict = dict[str,Form]

def get_forms(node: lxml.etree._Element, entry_id: str, form_id: str = None) -> FormDict:
    dict = FormDict()
    for form_node in node.xpath("tei:form", namespaces = NAMESPACES):
        form = Form()
        form["db_id"] = form_node.xpath("@xml:id",namespaces = NAMESPACES)[0]
        form["entry_id"] = entry_id
        form["orth"] = form_node.xpath("string(tei:orth)",namespaces = NAMESPACES)
        form["lang"] = form_node.xpath("ancestor-or-self::*[@xml:lang][1]/@xml:lang",namespaces = NAMESPACES)[0]
        
        form["rel_of"] = None
        form["rel_type"] = None
        if form_id:
            form["rel_of"] = form_id
            if form_node.xpath("@type", namespaces = NAMESPACES)[0] == 'variant':
                form["rel_type"] = FormRelType.VARIANT
            elif form_node.xpath("@type", namespaces = NAMESPACES)[0] == 'participle':
                form["rel_type"] = FormRelType.PARTICIPLE
        dict[form["db_id"]] = form
        dict = dict | get_forms(node = form_node, entry_id = entry_id, form_id = form["db_id"])
    return dict


# Only bottom-level senses are treated as actual senses. Sense 'groups' are viewed as IDs that are attached to individual senses. 
# These are stored as dictionaries that map the sense group ID to entry ID
class Sense(TypedDict):
    db_id: str # Should be the same as XML id
    entry_id: str # db_id of the entry
    lang: str = None # Language ID, if has 
    description_ru: str
    description_en: str
    is_def: bool = False # True if this is a definition, not translation in quotes
    sense_group: str = None # ID of the sense group that this belongs to
    num: int = None # If group has a number

SenseDict = dict[str,Sense]

class SenseGroup(TypedDict):
    db_id: str # Should be the same as XML id
    entry_id: str #db_id of the entry
    num: int = None # if it has a number

SenseGroupDict = dict[str,SenseGroup]

def get_senses(node: lxml.etree._Element, entry_id: str) -> Tuple[SenseDict,SenseGroupDict]:
    sense_dict = SenseDict()
    sense_group_dict = SenseGroupDict()
    for sense_node in node.xpath("tei:sense", namespaces = NAMESPACES):
        lang = None
        lang_supersense = sense_node.xpath("@xml:lang", namespaces = NAMESPACES)
        if len(lang_supersense) > 0:
            lang = lang_supersense[0]
        num = None
        num_supersense = sense_node.xpath("@n", namespaces = NAMESPACES)
        if len(num_supersense) > 0:
            num = num_supersense[0]        
        subsenses = sense_node.xpath("tei:sense", namespaces = NAMESPACES)
        if len(subsenses) > 0:
            sense_group = SenseGroup()
            group_id = sense_node.xpath("@xml:id", namespaces = NAMESPACES)[0]
            sense_group["db_id"] = group_id
            sense_group["entry_id"] = entry_id
            sense_group["num"] = num
            sense_group_dict[sense_group["db_id"]] = sense_group
            for subsense_node in subsenses:
                subsense = Sense()
                subsense["db_id"] = subsense_node.xpath("@xml:id", namespaces = NAMESPACES)[0]
                subsense["entry_id"] = entry_id
                subsense["sense_group"] = group_id
                lang_subsense = subsense_node.xpath("@xml:lang", namespaces = NAMESPACES)
                if len(lang_subsense) > 0:
                    lang = lang_subsense[0]
                subsense["lang"] = lang
                subsense["num"] = num

                subsense["is_def"] = False

                tr_ru = subsense_node.xpath("string(abv:tr[@xml:lang='ru']/tei:q)", namespaces = NAMESPACES)
                if tr_ru is not None:
                    subsense["description_ru"] = normalize(tr_ru)

                tr_en = subsense_node.xpath("string(abv:tr[@xml:lang='en']/tei:q)", namespaces = NAMESPACES)
                if tr_en is not None:
                    subsense["description_en"] = normalize(tr_en)
                else:
                    def_ru = subsense_node.xpath("string(tei:def[@xml:lang='ru'])", namespaces = NAMESPACES)
                    if def_ru is not None:
                        subsense["description_ru"] = normalize(def_ru)
                        subsense["is_def"] = True

                    def_en = subsense_node.xpath("string(tei:def[@xml:lang='en'])", namespaces = NAMESPACES)
                    if def_en is not None:
                        subsense["description_en"] = normalize(def_en)
                        subsense["is_def"] = True

                sense_dict[subsense["db_id"]] = subsense
        else:
            sense = Sense()
            sense["db_id"] = sense_node.xpath("@xml:id", namespaces = NAMESPACES)[0]
            sense["entry_id"] = entry_id
            sense["lang"] = lang
            sense["num"] = num
            sense["sense_group"] = None

            sense["is_def"] = False

            tr_ru = sense_node.xpath("string(abv:tr[@xml:lang='ru']/tei:q)", namespaces = NAMESPACES)
            if tr_ru is not None:
                sense["description_ru"] = normalize(tr_ru)

            tr_en = sense_node.xpath("string(abv:tr[@xml:lang='en']/tei:q)", namespaces = NAMESPACES)
            if tr_en is not None:
                sense["description_en"] = normalize(tr_en)

            else:
                def_ru = sense_node.xpath("string(tei:def[@xml:lang='ru'])", namespaces = NAMESPACES)
                if def_ru is not None:
                    sense["description_ru"] = normalize(def_ru)
                    sense["is_def"] = True

                def_en = sense_node.xpath("string(tei:def[@xml:lang='en'])", namespaces = NAMESPACES)
                if def_en is not None:
                    sense["description_en"] = normalize(def_en)
                    sense["is_def"] = True

            sense_dict[sense["db_id"]] = sense
    return (sense_dict, sense_group_dict)

# Same mechanism for example groups as for sense groups
class Example(TypedDict):
    db_id: str # Should be the same as XML id
    entry_id: str #db_id of the entry
    example_group: str # Reference to the ID of the group this is part of
    lang: str # Language ID
    text: str
    tr_ru: str
    tr_en: str

ExampleDict = dict[str,Example]

class ExampleGroup(TypedDict):
    db_id: str # Should be the same as XML id
    entry_id: str # db_id of the entry
    num: int = None

ExampleGroupDict = dict[str,ExampleGroup]

def get_examples(node: lxml.etree._Element, entry_id: str) -> Tuple[ExampleDict,ExampleGroupDict]:
    example_dict = ExampleDict()
    example_group_dict = ExampleGroupDict()
    for group_node in node.xpath("abv:exampleGrp", namespaces = NAMESPACES):
        group = ExampleGroup()
        group_id = group_node.xpath("@xml:id", namespaces = NAMESPACES)[0]
        group["db_id"] = group_id
        group["entry_id"] = entry_id
        num = None
        num_group = group_node.xpath("@n", namespaces = NAMESPACES)
        if len(num_group) > 0:
            num = num_group[0]
        group["num"] = num
        example_group_dict[group_id] = group

        examples = group_node.xpath("abv:example", namespaces = NAMESPACES)
        for example_node in examples:
            extext = example_node.xpath("tei:quote", namespaces = NAMESPACES)[0]
            if extext.text is not None:
                example = Example()
                example["db_id"] = example_node.xpath("@xml:id", namespaces = NAMESPACES)[0]
                example["entry_id"] = entry_id
                example["example_group"] = group_id
                lang = None
                lang_example = example_node.xpath("@xml:lang", namespaces = NAMESPACES)
                if len(lang_example) > 0:
                        lang = lang_example[0]
                example["lang"] = lang
                example["num"] = num
                example["text"] = normalize(extext.xpath("string()", namespaces = NAMESPACES))

                tr_ru_txt = None
                tr_ru = example_node.xpath("string(abv:tr[@xml:lang='ru']/tei:q)", namespaces = NAMESPACES)
                if tr_ru is not None:
                    tr_ru_txt = normalize(tr_ru)
                example["tr_ru"] = tr_ru_txt

                tr_en_txt = None
                tr_en = example_node.xpath("string(abv:tr[@xml:lang='en']/tei:q)", namespaces = NAMESPACES)
                if tr_en is not None:
                    tr_en_txt = normalize(tr_en)
                example["tr_en"] = tr_en_txt

                example_dict[example["db_id"]] = example
    return (example_dict, example_group_dict)

class Mentioned(TypedDict):
    db_id: str # Not necessarily the same as XML id (if several are unified into one)
    xml_id: list(str) # List of equivalent XML ids
    entry_id: str # Entry or entries in which this mentioned form appears
    langs: list(str) # Language ID
    form: list(str) # May include multiple words
    gloss_ru: list(str) # May include multiple glosses
    gloss_en: list(str) # May include multiple glosses
    same_as: str = None # If equivalent to another entry

MentionedDict = dict[str,Mentioned]

def get_mentioneds(node: lxml.etree._Element, entry_id: str) -> MentionedDict:
    dict = MentionedDict()
    word_elem = "*[name() = 'w' or name() = 'm' or name() = 'cl' or name() = 'phr' or name() = 's']"
    for node_m in node.xpath("//tei:etym[@xml:lang='ru']//tei:mentioned", namespaces = NAMESPACES):
        words = node_m.xpath(word_elem + "[text()]", namespaces = NAMESPACES)
        if len(words) > 0:
            mentioned = Mentioned()

            ru_id = str(node_m.xpath("@xml:id", namespaces = NAMESPACES)[0])
            mentioned["db_id"] = ru_id
            mentioned["xml_id"] = [ru_id]
            
            en_id = None
            node_en = None
            corresp = node_m.xpath("@corresp", namespaces = NAMESPACES)
            if len(corresp) > 0:
                en_id = corresp[0][1:]
                node_en = node_m.xpath("//tei:mentioned[@xml:id='" + en_id + "']", namespaces = NAMESPACES)[0]
                mentioned["xml_id"].append(en_id)
            
            mentioned["entry_id"] = entry_id
            
            langs = node_m.xpath("@xml:lang", namespaces = NAMESPACES)
            extralang = node_m.xpath("@extralang", namespaces = NAMESPACES)
            if len(extralang) > 0:
                langs = langs + extralang[0].split()
            mentioned["lang"] = langs
            
            mentioned["form"] = []
            for node_w in words:
                w = normalize(node_w.xpath("string()",namespaces = NAMESPACES))
                if node_w.xpath("@type = 'rec'",namespaces = NAMESPACES):
                    w = '*' + w
                mentioned["form"].append(w)
            
            glosses_ru = []
            for gloss_node in node_m.xpath("tei:gloss", namespaces = NAMESPACES):
                quoted_nodes = gloss_node.xpath("tei:q", namespaces = NAMESPACES)
                if len(quoted_nodes) > 0:
                    for quote in quoted_nodes:
                        glosses_ru.append(normalize(quote.xpath("string()", namespaces = NAMESPACES)))
                else:
                    gloss_text = gloss_node.xpath("string()", namespaces = NAMESPACES)
                    if gloss_text is not None:
                        glosses_ru.append(normalize(gloss_text))
            mentioned["gloss_ru"] = glosses_ru
            
            glosses_en = []
            if node_en is not None:
                for gloss_node in node_en.xpath("tei:gloss", namespaces = NAMESPACES):
                    quoted_nodes = gloss_node.xpath("tei:q", namespaces = NAMESPACES)
                    if len(quoted_nodes) > 0:
                        for quote in quoted_nodes:
                            glosses_en.append(normalize(quote.xpath("string()", namespaces = NAMESPACES)))
                    else:
                        gloss_text = gloss_node.xpath("string()", namespaces = NAMESPACES)
                        if gloss_text is not None:
                            glosses_en.append(normalize(gloss_text))
            mentioned["gloss_en"] = glosses_en
            dict[ru_id] = mentioned
    for node_m in node.xpath("//tei:etym[@xml:lang='en']//tei:mentioned[not(@corresp)]", namespaces = NAMESPACES):
        words = node_m.xpath(word_elem + "[text()]", namespaces = NAMESPACES)
        if len(words) > 0:
            mentioned = Mentioned()
            
            en_id = str(node_m.xpath("@xml:id", namespaces = NAMESPACES)[0])
            mentioned["db_id"] = en_id
            mentioned["xml_id"] = [en_id]        

            langs = node_m.xpath("@xml:lang", namespaces = NAMESPACES)
            extralang = node_m.xpath("@extralang")
            if len(extralang) > 0:
                langs = langs + extralang[0].split()
            mentioned["lang"] = langs
            
            mentioned["form"] = []
            for node_w in words:
                w = normalize(node_w.xpath("string()",namespaces = NAMESPACES))
                if node_w.xpath("@type = 'rec'",namespaces = NAMESPACES):
                    w = '*' + w
                mentioned["form"].append(w)

            glosses_en = []
            for gloss_node in node_m.xpath("tei:gloss", namespaces = NAMESPACES):
                quoted_nodes = gloss_node.xpath("tei:q", namespaces = NAMESPACES)
                if len(quoted_nodes) > 0:
                    for quote in quoted_nodes:
                        glosses_en.append(normalize(quote.xpath("string()", namespaces = NAMESPACES)))
                else:
                    glosses_en.append(normalize(gloss_node.xpath("string()", namespaces = NAMESPACES)))
            mentioned["gloss_en"] = glosses_en
            dict[en_id] = mentioned
    return dict

def abaev_key(x):
    x = x.replace('entry_','')
    #print (x)
    
    # Remove initial punctuation which does not influence order
    if x[0] == '7' or x[0] == '-' or x[0] =='8' or x[0] == '6':
        x = x[1:]
    
    # Remove word-internal punctuation and accent marks (a bit redundant but let it be)
    x = x.replace('6','')
    x = x.replace('9','')
    x = x.replace('-','')
    x = x.replace('_','')
    x = x.replace('́','') #combining acute
    x = x.replace('1','')
    x = x.replace('2','')
    x = x.replace('3','')
    x = x.replace('4','')
    x = x.replace('5','')
    
    
    x = x.replace('a','/')
    x = x.replace('A', '/')
    x = x.replace('ā', '/')
    x = x.replace('Ā', '/')
    x = x.replace('á', '/')
    x = x.replace('Á', '/')
    x = x.replace('ā́', '/')
    x = x.replace('Ā́', '/')
    
    x = x.replace('æ', '1')
    x = x.replace('Æ', '1')
    x = x.replace('ǽ', '1')
    x = x.replace('Ǽ', '1')    
    
    x = x.replace('b', '2')
    x = x.replace('B', '2')
    
    x = x.replace('cʼ', '4')
    x = x.replace('Cʼ', '4')
    
    x = x.replace('c', '3')
    x = x.replace('C', '3')
    
    x = x.replace('d', '5')
    x = x.replace('D', '5')
    
    x = x.replace('ʒ', '6')
    x = x.replace('Ʒ', '6')
    
    x = x.replace('e', '7')
    x = x.replace('E', '7')
    x = x.replace('é', '7')
    x = x.replace('É', '7')    
    
    x = x.replace('f', '8')
    x = x.replace('F', '8')

    x = x.replace('g0', '9')
    x = x.replace('G0', '9')
    
    x = x.replace('g', '9')
    x = x.replace('G', '9')
    
    x = x.replace('ǵ', '9')
    x = x.replace('Ǵ', '9')

    x = x.replace('ǧ0', 'A')
    x = x.replace('Ǧ0', 'A')
    
    x = x.replace('ǧ', 'A')
    x = x.replace('Ǧ', 'A')
    
    x = x.replace('i', 'B')
    x = x.replace('I', 'B')
    x = x.replace('í', 'B')
    x = x.replace('Í', 'B')
    
    x = x.replace('ī', 'B')
    x = x.replace('Ī', 'B')
    x = x.replace('ī́', 'B')
    x = x.replace('Ī́', 'B')    
    
    x = x.replace('j', 'D')
    x = x.replace('J', 'D')

    x = x.replace('kʼ0', 'F')
    x = x.replace('Kʼ0ʼ', 'F')

    x = x.replace('kʼ', 'F')
    x = x.replace('Kʼ', 'F')

    x = x.replace('k0', 'E')
    x = x.replace('K0', 'E')
    
    x = x.replace('k', 'E')
    x = x.replace('K', 'E')

    x = x.replace('ḱʼ', 'F')
    x = x.replace('Ḱʼ', 'F')
    
    x = x.replace('ḱ', 'E')
    x = x.replace('Ḱ', 'E')

    x = x.replace('l', 'H')
    x = x.replace('L', 'H')
    
    x = x.replace('m', 'I')
    x = x.replace('M', 'I')
    
    x = x.replace('n', 'J')
    x = x.replace('N', 'J')
    
    x = x.replace('o', 'K')
    x = x.replace('O', 'K')
    x = x.replace('ó', 'K')
    x = x.replace('Ó', 'K')    
    
    x = x.replace('pʼ', 'M')
    x = x.replace('Pʼ', 'M')    
    
    x = x.replace('p', 'L')
    x = x.replace('P', 'L')

    x = x.replace('q0', 'N')
    x = x.replace('Q0', 'N')
    
    x = x.replace('q', 'N')
    x = x.replace('Q', 'N')

    x = x.replace('r', 'O')
    x = x.replace('R', 'O')
    
    x = x.replace('s', 'P')
    x = x.replace('S', 'P')

    x = x.replace('tʼ', 'R')
    x = x.replace('Tʼ', 'R')
    
    x = x.replace('t', 'Q')
    x = x.replace('T', 'Q')
    
    x = x.replace('u', 'S')
    x = x.replace('U', 'S')
    x = x.replace('ú', 'S')
    x = x.replace('Ú', 'S')    
    
    x = x.replace('ū', 'S')
    x = x.replace('Ū', 'S')
    x = x.replace('ū́', 'S')
    x = x.replace('Ū́', 'S')    
    
    x = x.replace('v', 'T')
    x = x.replace('V', 'T')
    
    x = x.replace('w', 'U')
    x = x.replace('W', 'U')

    x = x.replace('x0', 'V')
    x = x.replace('X0', 'V')
    
    x = x.replace('x', 'V')
    x = x.replace('X', 'V')
    
    x = x.replace('y', 'W')
    x = x.replace('Y', 'W')
    x = x.replace('ý', 'W')
    x = x.replace('Ý', 'W')    
    
    x = x.replace('z', 'X')
    x = x.replace('Z', 'X')
    
    #return ''.join(abaev_alphabet.get(ch, ch) for ch in x)
    return x    

def serialize_dict(dict: dict[str,dict], file):
    fieldnames = list(list(dict.values())[0].keys())
    csv_writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=',')
    csv_writer.writeheader()
    for key in dict:
        row = {k:v for (k,v) in dict[key].items()}
        for key in row:
            if type(row[key]) is list:
                row[key] = ",".join(row[key])
            if isinstance(row[key], Enum):
                row[key]=row[key].value
        csv_writer.writerow(row)

langdata = LanguageDict.from_csv("../abaev-tei-oxygen/css/langnames.csv")
entries = EntryDict()
forms = FormDict()
senses = SenseDict()
senseGroups = SenseGroupDict()
examples = ExampleDict()
exampleGroups = ExampleGroupDict()
mentioneds = MentionedDict()
dir = "../abaevdict-tei/entries"
for file in os.listdir(dir):
    if file.endswith(".xml") and not(file.startswith("abaev_!")):
        entry_file = open(os.path.join(dir,file),"r")
        tree = etree.parse(entry_file)
        entry_file.close()

        node = tree.xpath("//tei:entry",namespaces=NAMESPACES)[0]

        entry = get_entry(node)
        entries[entry["db_id"]] = entry

        forms = forms | get_forms(node, entry["db_id"])
        
        senseTuple = get_senses(node, entry["db_id"])
        senses = senses | senseTuple[0]
        senseGroups = senseGroups | senseTuple[1]

        exampleTuple = get_examples(node, entry["db_id"])
        examples = examples | exampleTuple[0]
        exampleGroups = exampleGroups | exampleTuple[1]

        mentioneds = mentioneds | get_mentioneds(node, entry["db_id"])

sorted_keys = sorted(entries, key=abaev_key)
sorted_entries = {key:entries[key] for key in sorted_keys}

with open("entries.csv", "w") as file:
    serialize_dict(sorted_entries,file)
with open("forms.csv", "w") as file:
    serialize_dict(forms,file)
with open("senses.csv", "w") as file:
    serialize_dict(senses,file)
with open("senseGroups.csv", "w") as file:
    serialize_dict(senseGroups,file)
with open("examples.csv", "w") as file:
    serialize_dict(examples,file)    
with open("exampleGroups.csv", "w") as file:
    serialize_dict(exampleGroups,file)
with open("mentioneds.csv", "w") as file:
    serialize_dict(mentioneds,file)    