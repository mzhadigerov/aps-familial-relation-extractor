from podder_task_foundation import Context


class NerUtils:
    context = None

    @staticmethod
    def set_context(ctx: Context):
        NerUtils.context = ctx

    @staticmethod
    def get_person_duplets(ner_target_texts: list, ner_model) -> list:
        """
        Retrieves person names from text, where there are exactly two names per text
        :param ner_target_texts: list of text segments
        :param ner_model: model to perform ner
        :return: list of lists of length 2, containing names of first and second person
        """
        person_label = NerUtils.context.config.get("parameters.person_label")

        person_duplets = []
        for doc in ner_model.pipe(ner_target_texts,
                                  disable=["tagger", "parser"]):
            named_entities = [(ent.text, ent.label_) for ent in doc.ents]
            if len(named_entities) == 0:
                person_duplets.append(None)
            else:
                persons = list(
                    filter(lambda x: person_label in x[1], named_entities))
                person_duplet = (persons[0][0],
                                 persons[1][0]) if len(persons) == 2 else None
                person_duplets.append(person_duplet)
        return person_duplets
