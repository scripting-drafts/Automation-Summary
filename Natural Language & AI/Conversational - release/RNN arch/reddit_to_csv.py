import praw
from praw.models import MoreComments
import csv
import re

reddit = praw.Reddit(
    client_id='Your Client ID',
    client_secret='Your Client Secret',
    user_agent='Your User Agent'
)

def multireplace(string, replacements, ignore_case=False):
    if ignore_case:
        def normalize_old(s):
            return s.lower()

        re_mode = re.IGNORECASE

    else:
        def normalize_old(s):
            return s

        re_mode = 0

    replacements = {normalize_old(key): val for key, val in replacements.items()}
    if ignore_case:
        replacements = dict((pair[0].lower(), pair[1]) for pair in sorted(replacements.items()))
    rep_sorted = sorted(replacements, key=lambda s: (len(s), s), reverse=True)
    rep_escaped = map(re.escape, rep_sorted)
    pattern = re.compile("|".join(rep_escaped), re_mode)
    return pattern.sub(lambda match: replacements[normalize_old(match.group(0))], string)

replacements = {
    '\t': '    ',
    '\n': ' ',
    ';': '',
    '&#x200B': ' ',
    '&nbsp': ' '
}

commentlist = []

all_posts = reddit.subreddit('all').hot(limit=7)

for each_post in all_posts:
    subs = reddit.subreddit(str(each_post.subreddit)).hot(limit=3)

    for sub in subs:
        if sub.num_comments != 0:
            submission = reddit.submission(str(sub.id))

            if submission.is_self == True:
                data = {}
                data['sub'] = str(sub.subreddit.display_name)
                data['title'] = multireplace(submission.title, replacements=replacements, ignore_case=True)
                data['id'] = submission.id
                data['author']= str(submission.author)
                data['body'] = multireplace(submission.selftext, replacements=replacements, ignore_case=True)#submission.selftext.replace('\t', ' ').replace('\n', ' ').replace('&#x200B', '').replace(';', '')#''.join(body.replace('\t', ' ').replace('\n', ' ').replace('&#x200B', '').replace('\"', ''))#.replace('&#x200B', '')#multireplace(submission.selftext, replacements=replacements, ignore_case=True)
                data['score'] = submission.score
                data['parent_id'] = 'root'

                commentlist.append(data)
                submission.comments.replace_more(limit=None)

                for comment in submission.comments.list():
                    if comment.author != None:
                        data = {}
                        data['sub'] = str(sub.subreddit.display_name)
                        data['title'] = multireplace(sub.title, replacements=replacements, ignore_case=True)
                        data['id'] = comment.id
                        data['author']= str(comment.author)
                        data['body'] = multireplace(comment.body, replacements=replacements, ignore_case=True)#comment.body.replace('\t', ' ').replace('\n', ' ').replace('&#x200B', '').replace(';', '')#''.join(body.replace('\t', ' ').replace('\n', ' ').replace('&#x200B', '').replace('\"', ''))#.replace('&#x200B', '')#multireplace(comment.body, replacements=replacements, ignore_case=True)
                        data['score'] = comment.score
                        data['parent_id'] = str(comment.parent_id)[3:]

                        commentlist.append(data)



keys = commentlist[0].keys()

with open('reddit-fetch.csv', 'w', encoding='utf_8_sig') as output_file: #, newline='', encoding='utf_8_sig'
    dict_writer = csv.DictWriter(output_file, keys, dialect='excel', delimiter='\t')
    dict_writer.writeheader()
    dict_writer.writerows(commentlist)
