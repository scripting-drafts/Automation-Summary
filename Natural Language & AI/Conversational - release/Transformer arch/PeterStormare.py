from functools import wraps
import logging
from telegram.ext.filters import Filters

from telegram.ext.messagehandler import MessageHandler
from settings import BOT_TOKEN
from telegram import Update
from telegram.ext import (Updater,
                          PicklePersistence,
                          CommandHandler,
                          CallbackQueryHandler,
                          CallbackContext,
                          ConversationHandler)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from pgpt import leonardo


EXPECT_NAME, EXPECT_BUTTON_CLICK = range(2)
NUMEXPR_MAX_THREADS = 12
LIST_OF_ADMINS = ['ints']
leo = leonardo()

class leonardo_handler:
    def __init__(self, update):
        self.leo = leonardo()
        reply = self.leo.leonardo_rx('Hello Peter!')
        update.message.reply_text(reply)

        return ConversationHandler.END

    def reply(self, update, input):
        return  ConversationHandler.END


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in LIST_OF_ADMINS:
            print("Unauthorized access denied for {}.".format(user_id))
            return
        return func(update, context, *args, **kwargs)
    return wrapped

@restricted
def start(update: Update, context: CallbackContext):
    ''' Replies to start command '''
    # leo = leonardo_handler()
    # reply = leo.leonardo_rx('Hello Leonardo')
    # update.message.reply_text(reply)
    return

@restricted
def set_name_handler(update: Update, context: CallbackContext):
    ''' Entry point of conversation  this gives  buttons to user'''

    button = [[InlineKeyboardButton("name", callback_data='name')]]
    markup = InlineKeyboardMarkup(button)

    # you can add more buttons here

    #  learn more about inline keyboard
    # https://github.com/python-telegram-bot/python-telegram-bot/wiki/InlineKeyboard-Example

    update.message.reply_text('Name button', reply_markup=markup)

    return EXPECT_BUTTON_CLICK

@restricted
def button_click_handler(update: Update, context: CallbackContext):
    ''' This gets executed on button click '''
    query = update.callback_query
    # shows a small notification inside chat
    query.answer(f'button click {query.data} recieved')

    if query.data == 'name':
        query.edit_message_text(f'You clicked on "name"')
        # asks for name, and prompts user to reply to it
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='Send your name', reply_markup=ForceReply())
        # learn more about forced reply
        # https://python-telegram-bot.readthedocs.io/en/stable/telegram.forcereply.html
        return EXPECT_NAME

@restricted
def name_input_by_user(update: Update, context: CallbackContext):
    ''' The user's reply to the name prompt comes here  '''
    name = update.message.text

    # saves the name
    context.user_data['name'] = name
    update.message.reply_text(f'Your name is saved as {name[:100]}')

    # ends this particular conversation flow
    return ConversationHandler.END

@restricted
def simple_reply(update: Update, context: CallbackContext):
    user_input = update.message.text
    answer = leo.leonardo_rx(user_input)
    update.message.reply_text(answer)

    return ConversationHandler.END

@restricted
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text(
        'Name Conversation cancelled by user. Bye. Send /set_name to start again')
    return ConversationHandler.END

@restricted
def get_name(update: Update, context: CallbackContext):
    ''' Handle the get_name command. Replies the name of user if found. '''
    value = context.user_data.get(
        'name', 'Not found. Set your name using /set_name command')
    update.message.reply_text(value)


if __name__ == "__main__":
    pp = PicklePersistence(filename='mybot')
    updater = Updater(token=BOT_TOKEN, persistence=pp)

    dispatcher = updater.dispatcher

    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)

    _handlers = {}

    # _handlers['start_handler'] = CommandHandler('start', start)
    _handlers['message_handler'] = MessageHandler(Filters.text, simple_reply)

        # _handlers['message_handler'] = ConversationHandler(
        # entry_points=[MessageHandler(Filters.text, simple_reply)],
    #     states={
    #         EXPECT_NAME: [MessageHandler(Filters.text, name_input_by_user)],
    #         EXPECT_BUTTON_CLICK: [CallbackQueryHandler(button_click_handler)]
    #     },
    #     fallbacks=[CommandHandler('cancel', cancel)]
    # )
    # _handlers['get_name'] = CommandHandler('get_name', get_name)

    for name, _handler in _handlers.items():
        print(f'Adding handler {name}')
        dispatcher.add_handler(_handler)

    try:
        updater.start_polling()
        updater.idle()
    except Exception:
        leo.cleanup()