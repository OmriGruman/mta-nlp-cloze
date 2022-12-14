import json
import re
import numpy as np
from random import shuffle

from time import time

start = time()

N_PRE = 3
N_POST = 3
BLANK = '__________'
PADDING = '#'
NUM_RANDOM_PREDICTIONS = 100


def find_cloze_context(cloze_text):
    cloze_text = ' '.join([PADDING] * N_PRE + [cloze_text] + [PADDING] * N_POST)
    prefixes = [match.group().lower().split() for match in re.finditer(fr'(\S+\s){{{N_PRE}}}(?={BLANK})', cloze_text)]
    suffixes = [match.group().lower().split() for match in re.finditer(fr'(?<={BLANK})(\s\S+){{{N_POST}}}', cloze_text)]

    return prefixes, suffixes


def find_context_in_window(window, context, candidate_words, probabilities):
    context_i, (pre, post) = context
    curr_context = pre + [window[N_PRE]] + post

    for context_size in range(N_PRE + N_POST, -1, -1):
        max_n_pre = min(context_size, N_PRE)
        min_n_pre = max(context_size - N_POST, 0)

        for n_pre in range(max_n_pre, min_n_pre - 1, -1):
            n_post = context_size - n_pre

            start_pos = N_PRE - n_pre
            end_pos = len(window) - (N_POST - n_post)
            sub_window = window[start_pos: end_pos]
            sub_context = curr_context[start_pos: end_pos]

            if sub_context == sub_window:
                probabilities[context_i, n_pre, n_post, candidate_words.index(window[N_PRE])] += 1


def evaluate_sliding_window(window, prefixes, suffixes, candidate_words, probabilities):
    if window[N_PRE] in candidate_words:
        for context in enumerate(zip(prefixes, suffixes)):
            find_context_in_window(window, context, candidate_words, probabilities)


def calc_word_occurrences_by_context(corpus, prefixes, suffixes, candidate_words):
    occurrences = np.zeros((len(prefixes), N_PRE + 1, N_POST + 1, len(candidate_words)))

    with open(corpus, 'r', encoding='utf-8') as f:
        window = [PADDING] * (N_PRE + 1 + N_POST)

        for i, line in enumerate(f):
            for word in line.split():
                window = window[1:] + [word]
                evaluate_sliding_window(window, prefixes, suffixes, candidate_words, occurrences)

            if i % 100000 == 0:
                print(f'[{(time() - start):.2f}] {i}')

        # scan N_POST tokens after the end of the file
        for n_post in range(N_POST):
            window = window[1:] + [PADDING]
            evaluate_sliding_window(window, prefixes, suffixes, candidate_words, occurrences)

    return occurrences


def find_best_candidate(current_context, context_size, taken_candidates):
    max_n_pre = min(context_size, N_PRE)
    min_n_pre = max(context_size - N_POST, 0)

    for n_pre in range(max_n_pre, min_n_pre - 1, -1):
        n_post = context_size - n_pre
        candidates = current_context[n_pre, n_post]
        np.put(candidates, taken_candidates, 0)

        if any(candidates[candidates != 0]):
            return np.argmax(candidates)

    return -1


def find_best_match(candidate_occurrences):
    taken_candidates = []
    best_match = np.full((candidate_occurrences.shape[0]), -1)

    for context_size in range(N_PRE + N_POST, -1, -1):
        for curr_context_i in range(candidate_occurrences.shape[0]):
            if best_match[curr_context_i] == -1:
                best_candidate = find_best_candidate(candidate_occurrences[curr_context_i],
                                                     context_size,
                                                     taken_candidates)
                best_match[curr_context_i] = best_candidate

                if best_candidate != -1:
                    taken_candidates.append(best_candidate)

    return best_match


def solve_cloze(cloze, candidates, lexicon, corpus):
    print(f'[{(time() - start):.2f}] starting to solve the cloze {cloze} with {candidates} using {lexicon} and {corpus}')

    with open(cloze, 'r', encoding='utf-8') as f:
        cloze_text = f.read().lower()
    with open(candidates, 'r', encoding='utf-8') as f:
        candidate_words = f.read().lower().split()

    prefixes, suffixes = find_cloze_context(cloze_text)
    assert len(prefixes) == len(candidate_words), "Candidates amount and Cloze amount aren't equal"

    word_occurrences = calc_word_occurrences_by_context(corpus, prefixes, suffixes, candidate_words)
    best_match = find_best_match(word_occurrences)

    return np.array(candidate_words)[np.array(best_match)]


def calc_prediction_accuracy(prediction, correct_words):
    return 100 * sum([pred_word == c_word for pred_word, c_word in zip(prediction, correct_words)]) / len(prediction)


def calc_random_chance_accuracy(candidates):
    with open(candidates, 'r', encoding='utf-8') as f:
        candidate_words = f.read().split()

    predictions = candidate_words.copy()
    sum_accuracies = 0.0

    for i in range(NUM_RANDOM_PREDICTIONS):
        shuffle(predictions)
        sum_accuracies += calc_prediction_accuracy(predictions, candidate_words)

    return sum_accuracies / NUM_RANDOM_PREDICTIONS


if __name__ == '__main__':
    with open('config.json', 'r') as json_file:
        config = json.load(json_file)

    solution = solve_cloze(config['input_filename'],
                           config['candidates_filename'],
                           config['lexicon_filename'],
                           config['corpus'])

    print(f'[{(time() - start):.2f}] cloze solution: {solution}')

    with open(config['candidates_filename'], 'r', encoding='utf-8') as f:
        candidate_words = f.read().lower().split()

    print(f'[{(time() - start):.2f}] solution accuracy: {calc_prediction_accuracy(solution, candidate_words):.2f}%')

    random_chance_accuracy = calc_random_chance_accuracy(config['candidates_filename'])

    print(f'[{(time() - start):.2f}] random change accuracy = {random_chance_accuracy:.2f}')
