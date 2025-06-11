wordlist1 = [word for word in open('../resources/spanish_words.txt', 'r')]
wordlist2 = [word for word in  open('../resources/spanish_words2.txt', 'r', encoding="utf8")]
wordlist2.extend(word for word in wordlist1 if word not in wordlist2)
wordlist2.sort()
wordlist2 = [word.lower() for word in wordlist2]

f = open('../resources/wordlist.txt', 'w')

for word in wordlist2:
    if len(word) > 1:
        f.write(word)

f.close()