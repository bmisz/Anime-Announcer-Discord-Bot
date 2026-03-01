from langdetect import detect
from datetime import datetime

def convert_epoch_to_local(unix_epoch_time):
    if unix_epoch_time == None:
        return None
    dt_unix = datetime.fromtimestamp(unix_epoch_time)
    formatted_time = dt_unix.strftime("%a %d %b, %I:%M%p")
    return formatted_time

def determine_english_title(synonym_list):
    for synonym in synonym_list:
        language_of_syn = detect(synonym)
        if language_of_syn == 'en':
            return synonym
    return None     # No synonyms were in english