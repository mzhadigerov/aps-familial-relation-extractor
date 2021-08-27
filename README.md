### Prerequisites:

```
python 3.0+
java 8+ (needs to be tested in machines without java)
poetry
ner model needs to be unziped into data/board_members_information_extractor/
```
[ner model](https://drive.google.com/file/d/1a6UtJVFNSX-uxb5WZ85SPDB_LWhJReHo/view?usp=sharing)

### Installation:

```
poetry install
```

### Test:
```
poetry run python -X utf8 manage.py board_members_information_extractor --input pdf="inp
ut/board_members_information_extractor/test_1.pdf" --output="output/board_members_information_extractor/outputfile.json"
```
