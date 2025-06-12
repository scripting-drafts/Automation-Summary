This project is based on the pyTorch Chatbot by Matthew Inkawhich  

# General Usage 

Run the scraper with reddit_to_csv.py, make pairs (pairs.txt) out of the csv file (reddit-fetch.csv) with extract-pairs.py and train your model with DL_Chatbot.py. For the sake of coherence in the conversations I recommend running the scraper on a single subreddit.

# Basic tuning for data modeling and training

line 84 -> Maximum number of words for a sentence to be included in the pairs list.  
line 143 -> Minimum repetition frequency for each word to be considered when populating the vocabulary.  
line 561 -> Comment if the training has to start from a checkpoint.*1  
line 562 -> Checkpoint from which the training has to continue.  
line 563 - 565 -> Uncomment if the training has to start from a checkpoint.*1  
571 / 573 -> Comment/Uncomment in case you want to run the chatbot on CPU.*2  
line 606 -> Seconds it takes to show the Loss and iteration number on terminal.  
line 607 -> Size of each part in which the model is divided.  
line 605 -> Number of the last iteration the Chatbot will listen to.*3  


*1 Or if the training is complete and you want to run the Chatbot.  
*2 It is highly recommended to do the training on a GPU. With default values you can run it quickly on a modest one.  
*3 Set to a previous than lastest iteration to check if the data got corrupted.

To run the Chatbot uncomment the last lines of the code below # CHAT # and skip the training.
