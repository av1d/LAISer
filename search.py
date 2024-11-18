import argparse
import configparser
import json
import logging
import random
import re
import requests
import sys
import threading
import time
from duckduckgo_search import DDGS
from flask import Flask, render_template, request, jsonify
from urllib.parse import urlparse
#logging.basicConfig(level=logging.ERROR)  # uncomment for debugging


#       dBP dBBBBBb     dBP.dBBBBP   dBBBP dBBBBBb
#                BB        BP                  dBP
#     dBP    dBP BB   dBP  `BBBBb  dBBP    dBBBBK
#    dBP    dBP  BB  dBP      dBP dBP     dBP  BB
#   dBBBBP dBBBBBBB dBP  dBBBBP' dBBBBP  dBP  dB'
#
#   Local AI Search by av1d

APPNAME = 'LAISer'
VERSION = '0.2'

### Changelog:
###
### 1. Added a timeout between queries because DuckDuckGo-Search (DDGS)
### is raising a 'duckduckgo_search.exceptions.RatelimitException'
### rate-limiteng error (something on DuckDuckGo changed?)
###
### 2. Changed syntax of calling the DDGS module.



def search(search_query: str, num_results_to_return: int) -> list:
    # perform a search on duckduckgo.

    results = DDGS().text(
        search_query,
        max_results=num_results_to_return
    )
    text_container = []
    for result in results[:num_results_to_return]:
        text = {
            'title': result['title'],
            'href': result['href'],
            'body': result['body'] # summary / meta
        }
        text_container.append(text)
        source_links.append(result['href'])
    return text_container # list of dictionaries

def news(search_query: str, num_results_to_return: int) -> list:
    # fetch the news from duckduckgo.

    results = DDGS().news(
        search_query,
        max_results=num_results_to_return
    )
    news_container = []
    for result in results[:num_results_to_return]:
        news = {
            'title': result['title'], # article title
            'url': result['url'],
            'body': result['body'], # summary
            'source': result['source'] # news outlet
        }
        news_container.append(news)
        source_links.append(result['url'])
    return news_container # list of dictionaries

def _wikipedia_summary(page_title: str) -> list:
    # Get Wikipedia page summary based on page title

    url = f"https://en.wikipedia.org/w/api.php?"\
          f"format=json&"\
          f"action=query&"\
          f"prop=extracts&"\
          f"exintro=&"\
          f"explaintext=&"\
          f"redirects=1&"\
          f"titles={page_title}"

    response = requests.get(url)
    data = response.json()

    # full summary text:
    text = next(iter(data['query']['pages'].values()))['extract']

    if TRIM_WIKIPEDIA_SUMMARY == True:
        sentences = text.split('.') # assumes there are no ?/!
        trimmed_text = '. '.join(sentences[:TRIM_WIKIPEDIA_LINES]) + '.'
        return [{'summary':trimmed_text}]
    else:
        return [{'summary':text}]

def wikipedia(search_arg) -> str:
    # returns plain text string of page summary

    def trim_url(url):
        parsed_url = urlparse(url)
        path = parsed_url.path
        last_part = path.rsplit('/', 1)[-1]
        return last_part

    # get the most relevant Wikipedia result from DuckDuckGo
    search_result = search(f"site:wikipedia.org {search_arg}", 1)
    # add the result to the overall source_links list
    source_links.append(search_result[0]['href'])
    # Get the Wikipedia page title
    wiki_page_title = trim_url(search_result[0]['href'])
    # Get the page summary based on that title
    summary = _wikipedia_summary(wiki_page_title)
    return summary

def wait_between_queries(timeout_duration = 0.2):
    """
    Waits the necessary time between queries. If you are still
    receiving rate-limiting errors, increase this one decimal point
    until it stops.
    """
    time.sleep(timeout_duration)

def perform_searches(search_query: str) -> list:

    print("Getting Wikipedia summary...") if not SILENT else None
    wikipedia_summary = wikipedia(search_query)
    wikipedia_summary = format_llama_request(
        wikipedia_summary,
        "wikipedia"
    )
    wait_between_queries()

    print("Getting search results...") if not SILENT else None
    search_result = search(search_query, SEARCH_RESULT_COUNT)
    search_result = format_llama_request(
        search_result,
        "search"
    )
    wait_between_queries()

    print("Getting news results...") if not SILENT else None
    news_result = news(search_query, NEWS_RESULT_COUNT)
    news_result = format_llama_request(
        news_result,
        "news"
    )
    wait_between_queries()

    search_results = {
        'wikipedia_summary': wikipedia_summary,
        'search_result': search_result,
        'news_result': news_result
    }

    return search_results

def _is_llama_online() -> bool:

    # check if the API we're using is online and reachable

    if API_TO_USE == 'llama.cpp':

        url = f"http://"\
              f"{LLAMA_IP}"\
              f":"\
              f"{LLAMA_PORT}"\
              f"/health"

        headers = {"Content-Type": "application/json"}

        try:
            response = requests.get(url, headers=headers)
        except Exception as e:
            print(f"There was an error connecting to {API_TO_USE}")
            return False

        if response.status_code == 200:
            response_json = response.json()
            if (
                "status" in response_json and
                response_json["status"] == "ok"
            ):
                print(
                    f"{API_TO_USE} is online."
                ) if not SILENT else None
                return True
        else:
            print(f"{API_TO_USE} is offline or returning a bad status!")
            return False

    if API_TO_USE == 'ollama':
        try:
            response = requests.get(OLLAMA_BASE_URL)
        except Exception as e:
            print(f"There was an error connecting to {API_TO_USE}")
            return False

        if response.status_code == 200:
            if response.text == 'Ollama is running':
                print(
                    f"{API_TO_USE} is online."
                ) if not SILENT else None
                return True
        else:
            print(f"{API_TO_USE} is offline or returning a bad status!")
            return False


def feed_the_llama(query: str) -> str:

    if API_TO_USE == 'llama.cpp':

        payload = {
            "prompt": query,
            "n_predict": 128
        }

        LLAMA_SERVER_URL = f"http://"\
                           f"{LLAMA_IP}"\
                           f":"\
                           f"{LLAMA_PORT}"\
                           f"/completion"

        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                LLAMA_SERVER_URL,
                json=payload,
                headers=headers
            )
        except Exception as e:
            error_msg = f"Error: {e}.\n\n"\
                        f"Is the llama.cpp server running?"
            print(error_msg)
            erroneous = {
                "success": False,
                "content": error_msg
            }
            return erroneous

        if response.status_code == 200:
            answer = response.json()
            successful = {
                "success": True,
                "content": answer['content']
            }
            return successful
        else:
            error_msg = f"Error: {response.status_code}"
            print(error_msg)
            erroneous = {
                "success": False,
                "content": error_msg
            }
            return erroneous

    if API_TO_USE == 'ollama':

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": query,
            "stream": False
        })

        try:
            response = requests.post(
                OLLAMA_URL,
                headers=headers,
                data=data
            )
        except Exception as e:
            error_msg = f"Error: {e}.\n\nIs the ollama server running?"
            print(error_msg)
            erroneous = {
                "success": False,
                "content": error_msg
            }
            return erroneous

        if response.status_code == 200:
            answer = response.json()
            successful = {
                "success": True,
                "content": answer['response']
            }
            return successful
        else:
            error_msg = f"Error: {response.status_code}"
            print(error_msg)
            erroneous = {
                "success": False,
                "content": error_msg
            }
            return erroneous

def format_llama_request(data: list, data_source: str) -> str:

    # Format all the results into neat markdown code blocks.

    if data_source == "search":
        search_result = "Web search results:\n```\n"
        for entry in data:
            title = entry['title']
            url = entry['href']
            meta = entry['body']
            search_result = f"{search_result}Page title: {title}\n"
            search_result = f"{search_result}URL: {url}\n"
            search_result = f"{search_result}Page meta: {meta}\n"
            search_result = f"{search_result}\n"
        search_result = f"{search_result}```\n"
        return search_result

    elif data_source ==  "news":
        news_result = "News search results:\n```\n"
        for entry in data:
            title = entry['title']
            url = entry['url']
            meta = entry['body']
            source = entry['source']
            news_result = f"{news_result}Page title: {title}\n"
            news_result = f"{news_result}URL: {url}\n"
            news_result = f"{news_result}Page meta: {meta}\n"
            news_result = f"{news_result}News source: {source}\n"
            news_result = f"{news_result}\n"
        news_result = f"{news_result}```\n"
        return news_result

    elif data_source ==  "wikipedia":
        wikipedia_summary = "Wikipedia:\n```\n"
        summary_data = data[0]['summary']
        wikipedia_summary = f"{wikipedia_summary}{summary_data}\n"
        wikipedia_summary = f"{wikipedia_summary}```\n"
        return wikipedia_summary

    elif data_source ==  "reddit":
        for x in data:
            dictionary = x
            if 'reply' in dictionary:
                dict_reply = dictionary['reply']
                print(f"Reply:\n{dict_reply}\n")
            if 'op' in dictionary:
                dict_op = dictionary['op']
                print(f"Original post:\n{dict_op}\n")

    else:
        print("Error: invalid data source")

def format_sources(collected_source_links: list) -> str:
    # format the 'source' links (search result links) depending
    # on type of search (cli or web-based)

    # set global so we can erase the links after processing
    global source_links

    # remove any duplicates
    collected_source_links = list(dict.fromkeys(collected_source_links))

    if SEARCH_TYPE == "web":

        sources = (
            "<ul id='sources' class='sources'>\n"
        ) # button to expand/collapse source links

        for link in collected_source_links: # create source links
            constructed_link = (
                f"<li class='source-item'>"
                f"<a href='{link}' target='_blank' class='source-link'>"
                f"{link}"
                f"</a>"
                f"</li>"
                f"\n"
            )
            sources = f"{sources} {constructed_link}"

        sources = f"{sources} </ul>"
        source_links = [] # initialize the links so they don't cache
        return sources

    if SEARCH_TYPE == "cli":
        sources = ""
        for link in collected_source_links:
            link = f"{link} \n"
            sources = f"{sources} {link}"
        source_links= [] # initialize the links so they don't cache
        return sources

def remove_incomplete_sentence(input_text: str) -> str:
    # remove last sentence if incomplete
    sentences = re.split(r'(?<=[.!?])\s+', input_text.strip())
    if len(sentences) > 0 and not re.search(r'[.!?]$', sentences[-1]):
        del sentences[-1]
    result = ' '.join(sentences)
    return result

def process_search_query(search_query: str) -> str:
    # do all the searchy things

    search_answers = perform_searches(search_query)

    # Extract search results
    wikipedia_summary = search_answers.get('wikipedia_summary', "")
    search_result = search_answers.get('search_result', "")
    news_result = search_answers.get('news_result', "")

    search_data = f"{wikipedia_summary}\n"\
                  f"{search_result}\n"\
                  f"{news_result}\n"

    return search_data

def generate_llamatize_text(search_query: str, search_data: str) -> str:
    # the prompt we give to the model with all of our search results.

    llamatize = (
        f"I performed a web search for `{search_query}`.\n"
        f"Formulate a response based upon my search results:\n\n"
        f"{search_data}\n"
        f"In addition, separately answer my question of "
        f"`{search_query}` "
        f"directly without considering the information I provided "
        f"previously. Finally, "
        f"provide a summary which considers both of your answers.\n"
    )

    return llamatize

def process_and_display_results(search_query: str) -> str:

    # if the api/server is online
    if _is_llama_online():

        search_data = process_search_query(search_query)

        llamatize = generate_llamatize_text(search_query, search_data)

        print("Feeding the llama... ^°π°^") if not SILENT else None
        answer = feed_the_llama(llamatize)

        if answer["success"] == False:
            # if there was an error, return it
            return answer["content"]
        else:
            # if it was successful, process incomplete sentences
            answer = remove_incomplete_sentence(answer["content"])
            return answer
    else:
        error_msg = (
            f"{API_TO_USE} server is offline or status is not 'ok'.\n"
            f"Please check your {API_TO_USE} settings.\n"
        )
        print(error_msg)
        return error_msg

def web_input(search_query: str) -> str:
    # put results into 'answer-response' div with the source links

    answer = process_and_display_results(search_query)

    sources = format_sources(source_links)

    answer_content = (
        "<div id='answer-response'>"
        f"{answer}"
        "</div>\n"
        f"{sources}"
    )

    print("Returning result...")
    return answer_content

def web_server() -> None:
    print(
        f"Starting server at: "
        f"http://{BINDING_ADDRESS}:{BINDING_PORT}"
    )

    # setup Flask
    app = Flask(__name__)
    app.name = f"{APPNAME} v{VERSION}"

    @app.route('/', methods=['GET', 'POST'])
    def index():

        return render_template('index.html')

    @app.route('/search', methods=['POST'])
    def web_search():

        start_time = time.time() # log the start time for stats

        question = request.form['input_text'] # input from web
        print(f"━━━━━━━━┫ Received web request: {question}")

        # if lock is acquired then this app is currently in use.
        # we can currently only handle one request at a time.
        if lock.locked():
            error_msg = "Sorry, I can only handle one request "\
                        "at a time and I'm currently busy."
            return jsonify({
                    'result': error_msg
            })

        # if this app is free to process a request
        with lock:
            answer = web_input(question)

        end_time = time.time()
        print(f"Completed in {end_time - start_time:.2f} seconds.")

        # finally, return the answer to the web client
        return jsonify({'result': answer})

    # start Flask
    app.run(
        host=BINDING_ADDRESS,
        port=BINDING_PORT
    )

def cli(search_query: str) -> None:
    answer = process_and_display_results(search_query)
    print("━━━━━━━━┫ ANSWER") if not SILENT else None
    print(answer)

    sources = format_sources(source_links)
    print("\nSOURCES:")
    print(sources)

def load_config() -> None:
    # load user settings

    parser = configparser.ConfigParser()
    parser.read('settings.ini')

    global BINDING_ADDRESS
    global BINDING_PORT
    global LLAMA_IP
    global LLAMA_PORT
    global OLLAMA_BASE_URL
    global OLLAMA_URL
    global OLLAMA_MODEL
    global API_TO_USE
    global SILENT
    global SEARCH_RESULT_COUNT
    global NEWS_RESULT_COUNT
    global TRIM_WIKIPEDIA_SUMMARY
    global TRIM_WIKIPEDIA_LINES

    BINDING_ADDRESS = parser.get(
        'laiser',
        'BINDING_ADDRESS'
    )

    BINDING_PORT = parser.get(
        'laiser',
        'BINDING_PORT'
    )

    LLAMA_IP = parser.get(
        'llamaCPP',
        'LLAMA_IP'
    )

    LLAMA_PORT = parser.get(
        'llamaCPP',
        'LLAMA_PORT'
    )

    OLLAMA_BASE_URL = parser.get(
        'ollama',
        'OLLAMA_BASE_URL'
    )

    OLLAMA_URL = parser.get(
        'ollama',
        'OLLAMA_URL'
    )

    OLLAMA_MODEL = parser.get(
        'ollama',
        'OLLAMA_MODEL'
    )

    API_TO_USE = parser.get(
        'default_API',
        'API_TO_USE'
    )

    SILENT = parser.getboolean(
        'status_messages',
        'silent'
    )

    SEARCH_RESULT_COUNT = parser.getint(
        'advanced',
        'SEARCH_RESULT_COUNT'
    )

    NEWS_RESULT_COUNT = parser.getint(
        'advanced',
        'NEWS_RESULT_COUNT'
    )

    TRIM_WIKIPEDIA_SUMMARY = parser.getboolean(
        'advanced',
        'TRIM_WIKIPEDIA_SUMMARY'
    )

    TRIM_WIKIPEDIA_LINES = parser.getint(
        'advanced',
        'TRIM_WIKIPEDIA_LINES'
    )

def arguments() -> str:
    # setup the argument parser
    parser = argparse.ArgumentParser(
        description=f"{APPNAME} v{VERSION} - Local AI Search"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--query',
        '-q',
        type=str,
        help='The query to search for'
    )
    group.add_argument(
        '--server',
        '-s',
        action='store_true',
        help='Connect to the server'
    )
    args = parser.parse_args()

    server = False
    if args.query:
        query = args.query
        return query
    elif args.server:
        return False
    else:
        parser.error("Either --query or --server must be specified.")

if __name__ == "__main__":

    # get command line arguments
    get_arguments = arguments()

    # load user settings
    load_config()

    # control access since currently only one instance can run at a time
    lock = threading.Lock()

    # set some globals
    global SEARCH_TYPE
    SEARCH_TYPE = "" # holds search type "cli" or "web"
    global source_links
    source_links = [] # list for holding cited links
    global results
    results = "" # holds search results

    # announce which API the user is using
    print(f"Using {API_TO_USE}") if not SILENT else None

    # server mode:
    if not get_arguments:
        SEARCH_TYPE = "web"
        web_server()
    # cli mode:
    else:
        SEARCH_TYPE = "cli"
        search_query = get_arguments
        if not search_query:
            sys.exit("Enter a search query enclosed in quotes.")
        else:
            start_time = time.time()
            cli(search_query)
            source_links = [] # initialize links so they don't cache
            end_time = time.time()
            print(
                f"Completed in {end_time - start_time:.2f} seconds."
            ) if not SILENT else None
