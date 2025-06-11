import itertools

letter_scores = {
    'A': 1, 'E': 1, 'I': 1, 'O': 1, 'U': 1, 'L': 1, 'N': 1, 'Ñ': 1, 'R': 1, 'S': 1, 'T': 1,
    'D': 2, 'G': 2,
    'B': 3, 'C': 3, 'M': 3, 'P': 3,
    'F': 4, 'H': 4, 'V': 4, 'W': 4, 'Y': 4,
    'K': 5,
    'J': 8, 'X': 8,
    'Q': 10, 'Z': 10
}

def scrabble_score(word):
    total_score = 0
    for letter in word.upper(): # Convert to uppercase for easier lookup
        total_score += letter_scores.get(letter, 0) # Use .get() to handle unknown letters
    return total_score

letters = ['Ñ', 'U', 'F', 'B', 'E', 'E', 'U']
letters = [letter.lower() for letter in letters]

vocab = open('../resources/wordlist.txt', 'r').read().split()

combinations = []
counter = len(letters)

while True:
    if counter != 1:
        combinations_1 = set(itertools.combinations(letters, counter))
        counter -= 1
    else:
        break

    combinations.extend(combinations_1)

valuable_combinations = []

for com in combinations:
    com = ''.join(com)
    if com in vocab:
        valuable_combinations.append(com)

print(valuable_combinations)
word_values = [(com, sum([letter_scores[letter] for letter in com.upper()])) for com in valuable_combinations]

for value in word_values:
    print(f'{value[0]}: {value[1]}')