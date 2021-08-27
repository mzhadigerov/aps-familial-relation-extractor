from podder_task_foundation import Context


class NreUtils:
    context = None

    @staticmethod
    def set_context(ctx: Context):
        NreUtils.context = ctx

    @staticmethod
    def get_familial_triplets(person_duplets: list,
                              ner_target_texts: list) -> list:
        """
        Retrieves list of familial triplets (person-1, person-2, familial-relationship). This
        function also adds the text segment to the resulting list, but it will be removed after testing.
        Note: lengths of person_duplets and ner_target_texts should be the same, so that it is easy to track indicies

        :param person_duplets: list of person duplets (person-1, person-2) or Nones, If there is no duplets.
        :param ner_target_texts: list of text segments, where person duplets are located.
        """
        person_label = NreUtils.context.config.get("parameters.person_label")
        familial_gazetteer = NreUtils.context.config.get(
            "parameters.familial_gazetteer")

        if len(person_duplets) != len(ner_target_texts):
            NreUtils.context.logger.error(
                "Lengths of persons list and texts list are not the same")
            raise Exception
        familial_triplets = []
        for i, duplet in enumerate(person_duplets):
            if duplet is not None:
                triplet = {
                    "person_1": duplet[0],
                    "person_2": duplet[1],
                    "keyword": "",
                    "label": "",
                    "text": ner_target_texts[i]
                }
                ner_target_texts[i].replace(duplet[0], person_label)
                ner_target_texts[i].replace(duplet[1], person_label)
                for label, words in familial_gazetteer.items():
                    for word in words:
                        if word in ner_target_texts[i] and len(word) > len(
                                triplet["keyword"]):
                            triplet["label"] = label
                            triplet["keyword"] = word
                if triplet["label"] != "":
                    familial_triplets.append(triplet)
        return familial_triplets
