# (c) 2022 Warren Usui
# Squirrels on Caffeine Project
# This code is licensed under the MIT license (see LICENSE.txt for details)
"""
Automated Sedecordle Solver

First make the four pick in STARTER.  Next find all words that can be solved
from those picks.  Next find all words that can be found based on information
gleaned from the later picks.  Finally, if the problem is not solved, scan
for a word that can uniquely filter out the remaining picks.
"""
# TO DO: It would be nice to add scrolling to the display
import os
from datetime import datetime
from time import sleep
import requests

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import chromedriver_autoinstaller

WEBSITE = "http://sedecordle.com"
STARTER = ["folds", "bumpy", "chive", "grant"]

#
# Section 1 -- Top half of WebInterface class.  Handle the first four
# words guessed and all the solutions determined by those guesses
#
class WebInterface():
    """
    Sedecordle word interface. Handle selenium related setup.  The first
    section also makes the initial guesses and finds unique answers based
    on those guesses.  Any ambiguities at that point are found by the code
    from handle_dup_cases and beyond.

    self variables saved:
    input -- list of keyboard input (guesses)
    new_entries -- dictionary of word lists that match pattern.  Key used is
                   the YG output from the first four guesses
    dup_words -- dictionary indexed by word position in the puzzle.  If a
                 word is not uniquely identified in the first pass, possible
                 words that fit this spot go here.
    guess_list-- list of allowed words for guesses
    driver -- Selenium driver
    """
    def __init__(self, website):
        self.input = []
        self.new_entries = {}
        self.dup_words = {}
        with open("allowed.txt", "r", encoding="UTF-8") as rfile:
            glist = rfile.read()
        self.guess_list = glist.split()
        self.wordtable = do_scan(STARTER, get_words())
        chromedriver_autoinstaller.install()
        options = webdriver.ChromeOptions()
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        self.driver = webdriver.Chrome(service=Service(), options=options)
        self.driver.get(website)
        self.driver.maximize_window()
        elem1 = self.driver.find_element(By.ID, "free")
        elem1.click()

    def add_word(self, word):
        """
        Add a word into the sedecordle grid.  Sends character by character
        data and saves the word in self.input

        @param word String word that is being guessed
        """
        for letter in word:
            elem = self.driver.find_element(By.ID, letter)
            elem.click()
        elem = self.driver.find_element(By.ID, "enter2")
        elem.click()
        self.input.append(word)

    def check_start(self, limitv=5):
        """
        Check the words in the grid against the intial guesses
        Changes new_entries and dup_word values.

        @param int limitv word length (default 5)
        """
        for word in range(1, 17):
            indx = self.chk_word_in_grid(word, limitv)
            tindex = '|'.join(indx)
            if len(self.wordtable[tindex]) == 1:
                self.add_word(self.wordtable[tindex][0])
                self.new_entries[word] = self.wordtable[tindex][0]
            else:
                self.dup_words[word] = self.wordtable[tindex]
        for _ in range(0, 2):
            if len(self.dup_words) > 0:
                self.handle_dup_cases()

    def chk_word_in_grid(self, word, limitv):
        """
        Extract the color (Yellow/Green) information from words in the grid

        @param String word word to check
        @param int limitv Length of word (default 5)
        """
        indx = []
        for guess in range(1, limitv):
            bcheck = self.driver.find_element(
                By.ID, f"box{word},{guess},1").text
            if bcheck == '':
                break
            boxes = []
            for letter in range(1, 6):
                bkgrnd = self.driver.find_element(
                    By.ID, f"box{word},{guess},{letter}"
                    ).get_attribute("style")
                if "(24, " in bkgrnd:
                    boxes.append(".")
                if "(255, " in bkgrnd:
                    boxes.append("Y")
                if "(0, " in bkgrnd:
                    boxes.append("G")
            indx.append(''.join(boxes))
        return indx

#
# Section 2 -- Handle cases that were not solved by the original four words
# but can be figured out by later picks.  To a certain extent, this is a case
# where 90% of the effort is spent on 10% of the cases.
#
    def handle_dup_cases(self):
        """
        At this point, scan all the unsolved words against later guesses
        """
        while len(self.dup_words) > 0:
            nwd = {}
            for entry in self.dup_words:
                answ = self.eval_next_lv(entry)
                if len(answ) == 1:
                    self.add_word(answ[0])
                    self.new_entries[entry] = answ[0]
                else:
                    nwd[entry] = answ
            if wsize(self.dup_words) == wsize(nwd):
                break
            if wsize(self.dup_words) > wsize(nwd):
                self.dup_words = nwd.copy()
        if len(self.dup_words) > 0:
            for chkword in self.guess_list:
                okay = True
                for indx in self.dup_words:
                    if not wcheckout(chkword, self.dup_words[indx]):
                        okay = False
                        break
                if okay:
                    self.add_word(chkword)
                    return
            print("We should not be here")
            self.driver.get_screenshot_as_file(
                os.sep.join(["data", "screenshot.png"]))
            out_txt = ", ".join(self.input)
            fname = os.sep.join(["data", "last_really_bad_run"])
            with open(fname, "w", encoding="UTF-8") as fdesc:
                fdesc.write(out_txt)
            self.driver.quit()

    def eval_next_lv(self, entry):
        """
        Evaluate the word list against all information in the grid

        @param integer entry index into the sedecordle grid
        @return list updated list of possible words
        """
        gpat = 5 * [""]
        ypat = 5 * [""]
        unused = ""
        for indx, sptrn in enumerate(self.chk_word_in_grid(entry, 22)):
            maybebad = ""
            for indx2, spce in enumerate(sptrn):
                lchar = self.input[indx][indx2]
                if spce == "Y":
                    if lchar not in ypat[indx2]:
                        ypat[indx2] += lchar
                if spce == "G":
                    gpat[indx2] = lchar
                if spce == ".":
                    if lchar not in unused:
                        maybebad += lchar
            unused += self.addbad(indx, sptrn, maybebad)
        ans_list = []
        for word in self.dup_words[entry]:
            if not check_b4_adding(word, gpat, ypat, unused):
                ans_list.append(word)
        return ans_list

    def addbad(self, indx, sptrn, maybebad):
        """
        Add to the unused character list

        @param integer indx index into the sedecordle word grid
        @param String sptrn word information from word grid
        @param String maybebad potentially bad letters
        @return String unused letters
        """
        letsunused = ""
        for lchr in maybebad:
            bad = True
            for indx2, spce in enumerate(sptrn):
                if spce != ".":
                    if self.input[indx][indx2] == lchr:
                        bad = False
            if bad:
                letsunused += lchr
        return letsunused

def check_b4_adding(word, gpat, ypat, unused):
    """
    Return True if:
        gpat indicates that a letter is green and a letter does not match
        ypat indicates that a letter is yellow and this letter matches or
            this letter is not found in the word
        the letter matches a letter known to be unused

    @param word String word to check
    @param gpat String Green pattern
    @param ypat String yellow pattern
    @param unused String unused letters
    @return True/False
    """
    bad = False
    for indx, letter in enumerate(gpat):
        if letter != '':
            if letter != word[indx]:
                return True
    for indx, ylets in enumerate(ypat):
        if ylets != '':
            for ltr in ylets:
                if ltr == word[indx]:
                    return True
                if ltr not in word:
                    return True
    for letter in word:
        if letter in unused:
            bad = True
            break
    return bad

def wsize(dict_o_lists):
    """
    Count the number of entries in the list values of a dictionary

    @param dictionary dictionary with lists as values
    @return int Total number of entries in all lists
    """
    counter = 0
    for entry in dict_o_lists:
        counter += len(dict_o_lists[entry])
    return counter

def wcheckout(guess, patterns):
    """
    Call get_yg_val for all words that we want to check.  Return true
    if all the YG patterns are unique (guaranteeing that we can make a
    correct guess for all words after this one)

    @param guess String word to guess
    @param patterns list of strings that we want to make sure form unique
           patterns
    @return True if all words in patterns are unique
    """
    yglist = []
    for poss_word in patterns:
        yglist.append(get_yg_val(poss_word, guess))
    if len(set(yglist)) == len(patterns):
        return True
    return False

def get_yg_val(poss_word, guess):
    """
    Generate the YG pattern for a guess so that we can compare words with
    information from the sedecordle output

    @param poss_word String word we assume to be the sedecordle word
    @param guess String a word we are comparing poss_word with
    @return String Yellow/Green/Black output from this comparison
    """
    yg_str = ""
    for indx, letter in enumerate(poss_word):
        if letter == guess[indx]:
            yg_str += "G"
        else:
            yg_str += "."
    nong = ""
    for indx, letter in enumerate(poss_word):
        if yg_str[indx] != "G":
            nong += letter
    for indx, letter in enumerate(poss_word):
        if letter != guess[indx]:
            if letter in nong:
                yg_str = yg_str[:indx] + "Y" + yg_str[indx + 1:]
    return yg_str

#
# Section 3 -- Handle the collecting of words used
#
def get_words():
    """
    Extract words from the answer list.  Possibly replace with direct
    screen scraping.  Right now, read from answers.txt file

    @return list List of all possible answer words (strings)
    """
    with open("answers.txt", "r", encoding="UTF-8") as fanswers:
        ostr = fanswers.read()
    return ostr.split()

def check_guess(word, guess):
    """
    Compare a word with a guess

    @param word String Word being checked
    @param guess String Word being guessed
    @return String Green/Yellow/Black letter indication pattern
    """
    retv = ''
    for indx, letter in enumerate(word):
        if guess[indx] == letter:
            retv += 'G'
        else:
            if guess[indx] in word:
                retv += 'Y'
            else:
                retv += '.'
    return retv

def gen_key(word, guesses):
    """
    Take guess results (Y/G/B patterns) and return a string to use as
    part of a key to index all words

    @param word String assumed word
    @param guesses list List of guesses
    """
    nkeys = []
    for guess in guesses:
        nkeys.append(check_guess(word, guess))
    return "|".join(nkeys)

def do_scan(wlist, anlist):
    """
    Scan a list of words for matches in another list

    @param wlist List Words to be guessed
    @param list of possible answer words
    @return dict Dictionary indexed by gen_key values of words corresponding
                 to that pattern
    """
    big_table = {}
    for wrd in anlist:
        tindx = gen_key(wrd, wlist)
        if tindx not in big_table:
            big_table[tindx] = [wrd]
        else:
            big_table[tindx].append(wrd)
    return big_table

#
# Section 4 -- Top level calling of everything.
#
def extract_data(field):
    """
    Write the allowed and answer files from data extracted from the
    sedecordle code

    @param filed str file name (allowed or answers)
    """
    from_loc = ''.join([field, ' = "'])
    wpage = requests.get("http://sedecordle.com")
    tfront = str(wpage.content)
    first_str = tfront[tfront.find(from_loc):]
    ret_data = first_str[0:first_str.find('".split(')]
    with open(''.join([field, ".txt"]), 'w', encoding="utf8") as fdesc:
        fdesc.write(ret_data[len(from_loc):])

def solve_it(wsite, display_time):
    """
    Main routine.  Pick the first four picks and then call the WebInterface
    routine to check out the rest of the words.

    Upon return, scan the background color of the page to determine if the
    puzzle was solved or unsolved.  Record the data (words picked).

    @param wsite String web site name
    @param display_time int number of seconds to linger on the last screen
    """
    extract_data('allowed')
    extract_data('answers')
    if not os.path.exists("data"):
        os.mkdir("data")
    w_interf = WebInterface(wsite)
    for word in STARTER:
        w_interf.add_word(word)
    w_interf.check_start()
    elem1 = w_interf.driver.find_element(By.ID, "body")
    bgc_info = elem1.value_of_css_property("background-color")
    header = "unsolved"
    if bgc_info.find("0, 128, 0,") > 0:
        header = "solved"
    out_txt = ", ".join(w_interf.input)
    fname = header + datetime.now().strftime("-%Y-%m-%d-%H-%M-%S")
    fname = os.sep.join(["data", fname])
    with open(fname, "w", encoding="UTF-8") as fdesc:
        fdesc.write(out_txt)
    w_interf.driver.get_screenshot_as_file(
        os.sep.join(["data", "screenshot.png"]))
    sleep(display_time)
    w_interf.driver.quit()

def squirrel_dorkle():
    """
    Run squirrel_dorkle.  Keep output for 30 seconds
    """
    solve_it(WEBSITE, 30)

if __name__ == "__main__":
    squirrel_dorkle()
