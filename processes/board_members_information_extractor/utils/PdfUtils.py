import re
from io import StringIO
from pathlib import Path

import camelot
import pandas
import pdfminer.psparser
from bs4 import BeautifulSoup
from camelot.core import Table
from numpy import allclose
from pandas import DataFrame
from podder_task_foundation import Context
from tika import parser


class PdfUtils:
    context = None

    @staticmethod
    def set_context(ctx: Context):
        PdfUtils.context = ctx

    @staticmethod
    def split_pdf_by_pages(pdf: Path) -> list:
        """
        Split pdf by pages. Each element is a text.

        pdf:
            pathlib.Path: path to pdf
        Returns:
            list: pdf, split by pages
        """
        page_split_pdf = []
        data = parser.from_file(str(pdf), xmlContent=True)
        xhtml_data = BeautifulSoup(data['content'], features="html.parser")
        for i, content in enumerate(
                xhtml_data.find_all('div', attrs={'class': 'page'})):
            _buffer = StringIO()
            _buffer.write(str(content))
            parsed_content = parser.from_buffer(_buffer.getvalue())
            text = parsed_content['content'].strip()
            page_split_pdf.append(text)
        return page_split_pdf

    @staticmethod
    def get_pages_with_target_tables(page_split_pdf: list) -> list:
        """
        List, containing tables of interest. Note: It expects that the tables have "姓名" and "职务"
        columns for "name" and "position", respectively.

        :param page_split_pdf: all pdf pages as list of strings
        :param context: application context
        :return: list: page numbers, where target tables are located
            Note: index starts with 1, not 0. Because camelot-py starts with 1
        """

        return [
            i + 1 for i, page in enumerate(page_split_pdf)
            if '\n' + PdfUtils.context.config.get(
                "parameters.table_column_names.name.chinese") in page and ' ' +
            PdfUtils.context.config.get(
                "parameters.table_column_names.position.chinese") + ' ' in page
        ]

    @staticmethod
    def _are_tables_united(table1: Table, table2: Table) -> bool:
        """
        Are two tables parts of the same table, that split into several pages?

        :param table1: first table (on the first page)
        :param table2: second table (on the second page)
        :return: True if two tables are parts of one big table, False otherwise
        """

        if table2['page'] == (table1['page'] + 1):
            if len(table2['cols']) == len(table1['cols']):

                # extract the vertical coordinates of the tables
                _, y_bottom_table1, _, _ = table1['_bbox']
                _, _, _, y_top_table2 = table2['_bbox']

                # If the first table ends in the last 15% of the page
                # and the second table starts in the first 15% of the page
                optimal_pdf_page_height = PdfUtils.context.config.get(
                    "parameters.optimal_pdf_page_height")
                if y_bottom_table1 < .15 * optimal_pdf_page_height and y_top_table2 > .85 * optimal_pdf_page_height:
                    table1_cols = table1['cols']
                    table2_cols = table2['cols']

                    table1_cols_width = [
                        col[1] - col[0] for col in table1_cols
                    ]
                    table2_cols_width = [
                        col[1] - col[0] for col in table2_cols
                    ]

                    # evaluate if the column widths of the two tables are similar

                    return allclose(table1_cols_width,
                                    table2_cols_width,
                                    atol=3,
                                    rtol=0)
        return False

    @staticmethod
    def _concat_spanned_table(spanned_table: Table, pdf: Path,
                              pdf_pages_len: int) -> DataFrame:
        """
        Concatenates this table with its "tails", from the next pages. Note: the function
        assumes, that the parts of the table will be the first tables on each page.

        :param spanned_table: table, that might have parts on the next pages
        :param pdf: path to pdf
        :param pdf_pages_len: number of pages in pdf
        :return: concatenated table (DataFrame), If parts were found, otherwise - the
        same table in form of DataFrame
        """
        table_parts = []

        def find_table_parts(table):
            page = table.__dict__['page']
            if page < pdf_pages_len:
                next_page_tables = camelot.read_pdf(str(pdf),
                                                    pages=str(page + 1))
                if len(next_page_tables) > 0:
                    first_row = next_page_tables[0].df.iloc[0].values
                    column_names = {
                        PdfUtils.context.config.get(
                            "parameters.table_column_names.name.chinese"),
                        PdfUtils.context.config.get(
                            "parameters.table_column_names.position.chinese")
                    }
                    if not (set(first_row)
                            & column_names) and PdfUtils._are_tables_united(
                                table.__dict__, next_page_tables[0].__dict__):
                        table_parts.append(next_page_tables[0])
                        find_table_parts(next_page_tables[0])

        find_table_parts(spanned_table)

        if len(table_parts) > 0:
            columns = spanned_table.df.columns.values
            for part in table_parts:
                part.df.columns = columns
                spanned_table = pandas.concat([spanned_table.df, part.df],
                                              ignore_index=True)
        else:
            spanned_table = spanned_table.df
        return spanned_table

    @staticmethod
    def get_target_tables(pdf: Path, pages_with_target_tables: list,
                          pdf_pages_len: int) -> list:
        """
        Finds and returns target tables. Note: the logic still relies on the assumption,
        that target tables contain "姓名" and "职务" columns for "name" and "position", respectively.

        :param pdf: path to pdf
        :param pages_with_target_tables: list of pages, where target tables are located
        :param pdf_pages_len: number of pages in pdf
        :return: DataFrames of target tables
        """

        tables = []
        if len(pages_with_target_tables) > 0:
            target_pages_str = ','.join(
                str(page) for page in pages_with_target_tables)
            try:
                tables = list(
                    camelot.read_pdf(str(pdf), pages=target_pages_str))
            except pdfminer.psparser.PSSyntaxError:
                PdfUtils.context.logger.error(
                    f"Pdf {pdf} is corrupted! Please read this thread to fix: "
                    "https://github.com/atlanhq/camelot/issues/161")
                raise
            wrong_tables_idx = []
            for i, table in enumerate(tables):
                first_row = table.df.iloc[0].values
                column_names = {
                    PdfUtils.context.config.get(
                        "parameters.table_column_names.name.chinese"),
                    PdfUtils.context.config.get(
                        "parameters.table_column_names.position.chinese")
                }
                if set(column_names).issubset(first_row):
                    table_df = table.df
                    table_df.columns = first_row
                    tables[i] = PdfUtils._concat_spanned_table(
                        table, pdf, pdf_pages_len
                    )  # This will search for `current_page + n` pages to concatenate multi-page tables
                else:
                    wrong_tables_idx.append(i)
            for idx in wrong_tables_idx:
                del tables[idx]

        return tables

    @staticmethod
    def get_board_members(tables: list) -> DataFrame:
        """
        Board Members (people in key positions), including "name" and "position" Note: it uses regExp
        to find matches among positions.

        :param tables: list of DataFrames, containing information about all employees
        :return:
        """
        column_name_chinese = PdfUtils.context.config.get(
            "parameters.table_column_names.name.chinese")

        column_position_chinese = PdfUtils.context.config.get(
            "parameters.table_column_names.position.chinese")

        column_name_english = PdfUtils.context.config.get(
            "parameters.table_column_names.name.english")

        column_position_english = PdfUtils.context.config.get(
            "parameters.table_column_names.position.english")

        board_members_positions_regex = PdfUtils.context.config.get(
            "parameters.board_members_positions_regex")

        final_table = DataFrame({
            column_name_english: [],
            column_position_english: []
        })
        for table in tables:
            table = table[[column_name_chinese, column_position_chinese]]
            table.columns = [column_name_english, column_position_english]
            match_people = table[table[column_position_english].str.contains(
                board_members_positions_regex) == True]
            if not match_people.empty:
                if final_table is None:
                    final_table = match_people
                else:
                    final_table = pandas.concat([final_table, match_people])
        final_table.reset_index(drop=True, inplace=True)

        return final_table

    @staticmethod
    def get_matching_segments(pdf_split_by_pages: list, texts: list) -> list:
        """
        Unique text segments, matching texts within target_parts
        :param pdf_split_by_pages: list of pdf pages
        :param texts: text to match
        :return: set of unique text segments
        """
        matched_segments = set()

        for page in pdf_split_by_pages:
            segmented_page = re.findall(r"[\w']+", page)
            ner_target_segments = set([
                segment for segment in segmented_page
                if any(bm_name in segment for bm_name in texts)
            ])
            matched_segments.update(ner_target_segments)
        return list(matched_segments)
