text = open('shakespeare.txt', 'r')

words = [x.split(' ') for x in text if x]

singleWords = []

for number in range(len(words)):
    for word in words[number]:
        if word and word != '\n':
            singleWords.append(word.replace(',', '').replace('\n', ''))

print(len(singleWords))
print(singleWords[:100])
