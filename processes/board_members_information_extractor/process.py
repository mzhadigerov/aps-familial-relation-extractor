from pathlib import Path

import spacy
from podder_task_foundation import Context, Payload
from podder_task_foundation import Process as ProcessBase

from .utils.NerUtils import NerUtils
from .utils.NreUtils import NreUtils
from .utils.PdfUtils import PdfUtils


class Process(ProcessBase):
    def initialize(self, context: Context) -> None:
        # Initialization need to be done here
        # Never do the initialization on execute method !
        # - Model loading
        # - Large text(json) file loading
        # - Prepare some data
        self.column_name_chinese = \
            context.config.get("parameters.table_column_names.name.chinese")
        self.column_position_chinese = \
            context.config.get("parameters.table_column_names.position.chinese")

        self.column_name_english = \
            context.config.get("parameters.table_column_names.name.english")

        self.column_position_english = \
            context.config.get("parameters.table_column_names.position.english")

        self.board_members_positions_regex = \
            context.config.get("parameters.board_members_positions_regex")

        self.optimal_pdf_page_height = \
            context.config.get("parameters.optimal_pdf_page_height")

        self._ner_model_file_path = Path(
            context.file.get_data_file(context.config.get("model.ner.chinese.path")))

        self.person_label = \
            context.config.get("parameters.person_label")

        self.familial_gazetteer = \
            context.config.get("parameters.familial_gazetteer")

        self.ner_model = spacy.load(self._ner_model_file_path)

    def execute(self, input_payload: Payload, output_payload: Payload,
                context: Context):
        pdf = input_payload.get(name="pdf", object_type="pdf")

        PdfUtils.set_context(context)
        NerUtils.set_context(context)
        NreUtils.set_context(context)

        pdf_split_by_pages = PdfUtils.split_pdf_by_pages(pdf.data)
        pages_with_target_tables = PdfUtils.get_pages_with_target_tables(
            pdf_split_by_pages)
        target_tables = PdfUtils.get_target_tables(
            pdf.data,
            pages_with_target_tables,
            pdf_pages_len=len(pdf_split_by_pages))
        board_members = PdfUtils.get_board_members(target_tables)
        familial_triplets = []
        if not board_members.empty:
            board_member_names = board_members['name'].unique()
            ner_target_texts = PdfUtils.get_matching_segments(
                pdf_split_by_pages, board_member_names)
            person_duplets = NerUtils.get_person_duplets(
                ner_target_texts, self.ner_model)
            familial_triplets = NreUtils.get_familial_triplets(
                person_duplets, ner_target_texts)
        # Output result
        output_payload.add_array(familial_triplets)
