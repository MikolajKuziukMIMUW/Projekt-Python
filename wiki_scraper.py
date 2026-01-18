# TODO comments
# TODO shorten loops to achieve a more functional program
# TODO debug everything precisely
# TODO break up into modules
# TODO non-functional requirements
# TODO license

import argparse
import json
import math

import numpy as np
import os
import pandas as pd
import re
import requests
import time

from bs4 import BeautifulSoup # One Big Beautiful Soup
# It's the most delicious soup I've ever had, probably the best since World War 2
# Not like the ones Biden used to make, those were an embarrassment

from matplotlib import pyplot as plt
from urllib.parse import quote, unquote
from wordfreq import word_frequency, top_n_list

def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument("--summary", help="scraping summary")

    parser.add_argument("--table", help="scraping table")
    parser.add_argument("--number", help="number of the table")
    # Not implementing --first-row-is-header, as that is marked there accordingly

    parser.add_argument("--count-words", help="counting words in text")

    parser.add_argument("--analyze-relative-word-frequency",
                        help="analyzing word frequency in the article compared to general")
    parser.add_argument("--mode",
                        help="mode for comparing frequencies")
    parser.add_argument("--count", help="count of words compared")
    parser.add_argument("--chart", help="path to the file with the chart")

    parser.add_argument("--auto-count-words", help="counting words in many articles")
    parser.add_argument("--depth", help="max depth of articles")
    parser.add_argument("--wait", help="time before the next article")

    return parser.parse_args()

class Scraper:
    def __init__(self, BASE_URL, LANG, article_name, use_local_html_file_instead):
        self.BASE_URL = BASE_URL
        self.LANG = LANG

        self.article_name = article_name
        self.url = self.BASE_URL + quote(article_name.replace(" ", "_"))
        self.use_local_html_file_instead = use_local_html_file_instead
        self.soup = self._fetch_soup()

    def _fetch_soup(self):
        if self.use_local_html_file_instead:
            file_path = self.article_name + ".html"
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return BeautifulSoup(html_content, "html.parser")

        try:
            response = requests.get(self.url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading the page: {e}")
            return None

    def get_first_paragraph(self):
        paragraphs = self.soup.select(".mw-parser-output p")
        if paragraphs:
            return paragraphs[0].get_text(separator=" ", strip=True)

        print("Paragraphs missing in the article contents")
        return None

    def save_table_to_csv(self, number):
        try:
            tables = pd.read_html(self.url, header=None)
            if tables and 0 < number <= len(tables):
                tables[number-1].to_csv(self.article_name + ".csv", index=False)
            else:
                print("Table with the given number not found")
        except requests.exceptions.RequestException as e:
            print(f"Error processing the table: {e}")


    def _get_word_counts(self):
        article = self.soup.select_one(".mw-parser-output")
        if not article:
            print("Article content not found")
            return {}
        for junk in article.select(".infobox, .navbox, .toc, .mw-editsection, table, .catlinks"):
            junk.decompose()
        text = article.get_text(separator=" ", strip=True)

        words = re.findall(r'\b\w+\b', text.lower(), flags=re.UNICODE)
        counts = {}
        for word in words:
            if word in counts:
                counts[word] = counts.get(word) + 1
            else: counts[word] = 1
        return counts

    def _load_json_data(self):
        if os.path.exists("./words-counts.json"):
            with open("./words-counts.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                data["runs"] += 1
        else:
            data = {"runs": 1, "words": {}}
        return data

    def _dump_json_data(self, data):
        with open("./words-counts.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def update_word_counts(self):
        data = self._load_json_data()
        counts = self._get_word_counts()
        for word, count in counts.items():
            data["words"][word] = data["words"].get(word, 0) + count
        self._dump_json_data(data)

    def _compare_words_to_wordfreq_article(self, n_words):
        counts_art = self._get_word_counts()
        sorted_counts_art = sorted(counts_art.items(), key=lambda x: x[1], reverse=True)[:n_words]
        max_count_art = sorted_counts_art[0][1]
        normalized_counts_art = {word: count / max_count_art for word, count in sorted_counts_art}

        counts_lang = {word: word_frequency(word, self.LANG) for word in normalized_counts_art.keys()}
        max_count_lang = word_frequency(top_n_list(self.LANG, 1)[0], self.LANG)
        normalized_counts_lang = {word: count / max_count_lang for word, count in counts_lang.items()}

        return normalized_counts_art, normalized_counts_lang

    def _compare_words_to_wordfreq_language(self, n_words):
        top_words_lang = top_n_list(self.LANG, n_words)
        counts_lang = {word: word_frequency(word, self.LANG) for word in top_words_lang}
        max_count_lang = word_frequency(top_words_lang[0], self.LANG)
        normalized_counts_lang = {word: count / max_count_lang for word, count in counts_lang.items()}

        counts_art = self._get_word_counts()
        sorted_counts_art = sorted(counts_art.items(), key=lambda x: x[1], reverse=True)[:n_words]
        normalized_counts_art = {word: counts_art[word] / sorted_counts_art[0][1] if word in counts_art else math.nan
                             for word in counts_lang.keys()}

        return normalized_counts_art, normalized_counts_lang

    def _plot_words_to_wordfreq(self, counts_art, counts_lang, chart):
        column_width = .3
        pos_art = np.arange(len(counts_art))
        pos_lang = [x + column_width for x in pos_art]

        plt.bar(pos_art, counts_art.values(), color="blue", width=column_width,
                label="Frequency in the article")
        plt.bar(pos_lang, counts_lang.values(), color="red", width=column_width,
                label="Frequency in the language")

        plt.xlabel("Words", fontweight="bold")
        plt.xticks((pos_art + pos_lang) / 2, counts_art.keys())
        plt.ylabel("Frequencies", fontweight="bold")
        plt.title("Frequencies of some words on Wookieepedia")
        plt.legend()

        plt.savefig(chart)

    def compare_words_to_wordfreq(self, mode, n_words, chart):
        if mode == "article":
            counts_art, counts_lang = self._compare_words_to_wordfreq_article(n_words)
        elif mode == "language":
            counts_art, counts_lang = self._compare_words_to_wordfreq_language(n_words)
        else:
            print("Error! Chose mode 'article' or 'language'!")
            return None

        if chart:
            self._plot_words_to_wordfreq(counts_art, counts_lang, chart)

        return pd.DataFrame(
            {"Frequency in the article": counts_art,
             "Frequency in the language": counts_lang})

    # TODO check if we're entering the same article twice
    def run_recursively(self, depth, wait):
        self.update_word_counts()
        if depth > 1:
            for a in self.soup.select(".mw-parser-output a[href]:not(.new)"):
                article_path = a["href"][6:]
                if ":" not in article_path and a["href"][:6] == "/wiki/":
                    next_article = unquote(article_path).replace("_", " ")
                    print(f"Redirecting to: {next_article}")
                    time.sleep(wait)
                    # TODO that could be different if we're analysing a local file instead:
                    next_scraper = Scraper(self.BASE_URL, self.LANG, next_article, self.use_local_html_file_instead)
                    next_scraper.run_recursively(depth - 1, wait)

class Manager:
    BASE_URL = "https://starwars.fandom.com/wiki/"
    LANG = "en"
    use_local_html_file_instead = False

    def __init__(self, args):
        self.args = args

    def _provide_license_information(self, pagename):
        # MANDATORY ATTRIBUTION PRINT
        print(f"Content from Wookieepedia: {pagename}")
        print(f"Source: {self.BASE_URL + quote(pagename.replace(" ", "_"))}")
        print("License: CC BY-SA 3.0")

    def _new_scraper(self, pagename):
        self._provide_license_information(pagename)
        return Scraper(self.BASE_URL, self.LANG, pagename, self.use_local_html_file_instead)

    def action(self):
        if self.args.summary:
            scraper = self._new_scraper(self.args.summary)
            print(scraper.get_first_paragraph())

        if self.args.table:
            if self.args.number:
                scraper = self._new_scraper(self.args.table)
                scraper.save_table_to_csv(int(self.args.number))
            else:
                print("Error! Usage: --table [PHRASE TO LOOK FOR] --number [N]")

        if self.args.count_words:
            scraper = self._new_scraper(self.args.count_words)
            scraper.update_word_counts()

        if self.args.analyze_relative_word_frequency:
            if self.args.mode and self.args.count:
                scraper = self._new_scraper(self.args.analyze_relative_word_frequency)
                print(scraper.compare_words_to_wordfreq(self.args.mode, int(self.args.count), self.args.chart))
            else:
                print("Error! Usage: --analyze-relative-word-frequency [PHRASE TO LOOK FOR] --mode [MODE] --count [N]")

        if self.args.auto_count_words:
            if self.args.depth and self.args.wait:
                scraper = self._new_scraper(self.args.auto_count_words)
                scraper.run_recursively(int(self.args.depth), float(self.args.wait))
            else:
                print("Error! Usage: --auto-count-words [STARTING PHRASE] --depth [N] --wait [T]")

def main():
    manager = Manager(parse_arguments())
    manager.action()

if __name__ == "__main__":
    main()
