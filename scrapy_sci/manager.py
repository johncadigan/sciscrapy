# -*- coding: utf-8 -*-

import os
from os import listdir
from os.path import isfile, join, isdir
from glob import glob
from collections import defaultdict
import sys
import re
import imp
import string
import inspect
import json
import new
import ConfigParser
import shutil

from os.path import join, exists, abspath
from shutil import copytree, ignore_patterns
from scrapy.utils.template import render_templatefile, string_camelcase

import sciscrapy
from sciscrapy.classifier import LogisticClassifier, ClassifierCreator
from sciscrapy.status import Status, Reader

TEMPLATES_PATH = join(sciscrapy.__path__[0], 'templates')
CLASSIFIERS_PATH = os.getcwd() + os.sep + "data"

TEMPLATES_TO_RENDER = (
    ('${classifier_name}', 'datafeatures.py.tmpl'),
)

IGNORE = ignore_patterns('*.pyc', '.svn')

class Manager(object):
    
    
    def __init__(self):
        self.status = Status()
        self.main_menu()
        
    
    def make_classifier_settings(self, classifier_name):
        config = ConfigParser.RawConfigParser()
        self.status.classifier_status(classifier_name)
        cont_work = True
        prompt = "0. Create new settings file\n1. Return to classifier menu"
        choice = int(raw_input(prompt))        
        while cont_work:
            if choice == 0:
                config = ConfigParser.RawConfigParser()
                names = ["none"]
                if self.status.classifiers[classifier_name]['info']['unreviewed']:
                    files = [re.findall('[a-z]*', s) for s in self.status.classifiers[classifier_name]['unreviewed']]
                    names = [item for sublist in files for item in sublist if len(re.findall("json|data|" +classifier_name, item))==0]
                print "Detected possible names " + " ".join(names)
                config.add_section("Classifier")
                classifications = raw_input("Please input classifications separated by commas\n").split(",")
                config.set("Classifier", "classes", ",".join(sorted(c.strip() for c in classifications)))
                for class_type in config.get("Classifier", "classes").split(","):
                    keep = int(raw_input("Collect data classified as {0}?\n1. Yes\n 2. No".format(class_type)))
                    if keep == 1: 
                        config.set("Classifier", class_type, True)
                    else:
                        config.set("Classifier", class_type, False)
                with open("data/{0}/settings.cfg".format(classifier_name), "wb") as configfile:                
                    config.write(configfile)
                    self.status.classifiers[classifier_name]['info']['settings'] = True
                    self.status.classifiers[classifier_name]['settings'] = configfile
                choice = 1
            elif choice == 1:
                cont_work = False
    
    def test_classifier(self, classifier_name):
        CC = ClassifierCreator(self.status.classifiers[classifier_name])
        prompt = "Possible options:\n"
        if CC.unreviewed: prompt+= "0. Train and test on unreviewed data\n"
        if CC.reviewed: prompt+= "1. Train and test on reviewed data\n"
        if CC.possible: prompt+= "2. Train and test with all possible data\n"
        prompt += "3. Return to classifier menu\n\n"
        cont_work = True
        while cont_work:
            choice = int(raw_input(prompt))
            if choice== 0 and CC.unreviewed:
                tests = int(raw_input("Please input number of desired test trials"))
                CC.create_data_set("unreviewed")
                lc = CC.create_classifier(LogisticClassifier)
                lc.estimate_accuracy(tests, verbose=True)
            elif choice== 1 and CC.reviewed:
                tests = int(raw_input("Please input number of desired test trials"))
                CC.create_data_set("reviewed")
                lc = CC.create_classifier(LogisticClassifier)
                lc.estimate_accuracy(tests, verbose=True)
            elif choice == 2:
                tests = int(raw_input("Please input number of desired test trials"))
                CC.create_data_set("both")
                lc = CC.create_classifier(LogisticClassifier)
                lc.estimate_accuracy(tests, verbose=True)
            elif choice == 3:
                cont_work = False
                
    #Review one file for one to many classifiers
    
    """FIX: update with new use of settings file and Reader"""
    def review_file(self, classifier_names, data_set, i_no = 0):
        #Setting up classifiers which are possible
        valid_classifiers = defaultdict(dict)#Dictionary for currently feasible classifiers only
        for classifier_name in classifier_names:
            classifications = []
            if self.status.classifiers[classifier_name]['info']['settings']:
                valid_classifiers[classifier_name]['classifications'] = \
                sorted(self.status.classifiers[classifier_name]['classifications'])
        #Counting files for valid classifiers
        no_files = {}
        classifiers = valid_classifiers.keys()
        for classifier in valid_classifiers.keys():
            reviewed = self.status.classifiers[classifier]['reviewed']
            for classification in list(valid_classifiers[classifier]['classifications']):
                no_files[classification] = len([x for x in reviewed if x.find(os.sep + classification) >= 0])
        print "Attempting to read data set"
        items = Reader.read_unreviewed(data_set)
        #Confirmation mode
        confirmation_mode = False
        conf_input = 2
        while conf_input > 1:
            try:
                conf_input = int(raw_input("0. Keep the same\n1. Turn on confirmation mode"))
            except:
                print "Wrong input"
            if conf_input == 1: confirmation_mode = True
        #Review of items
        n = i_no
        while n < len(items):
            print "ITEM {0}/{1}".format(n, len(items))
            print no_files
            item = items[n]
            self.status.item.review(item)
            if n >= i_no:
                to_write = {}
                for classifier in valid_classifiers.keys():
                    #Loop to ensure a choice
                    is_a_choice = False
                    while is_a_choice == False:
                        prompt= "Pick classification\n"
                        choices = {}
                        i = 0               
                        for classification in valid_classifiers[classifier]['classifications']:
                            i+=1
                            choices[i] = classification
                            prompt+= "{0}. {1}\t".format(i, classification)
                            if i % 3 == 0: prompt += "\n"
                        try:
                            choice = int(raw_input(prompt))
                        except:
                            print "Wrong input"
                        if choices.has_key(choice): is_a_choice = True
                    to_write[classifier] = choices[choice]
                confirmed = True
                if confirmation_mode:
                    confirmed = False
                    print "Choices: {0}".format("\t".join(to_write))
                    choice = 3
                    while choice < 0 and choice > 1:
                        try:
                            choice  = int(raw_input("0. Confirm \n 1. Reclassify"))
                        except:
                            print "Wrong input"
                        if choice == 0: confirmed = True
                if confirmed:
                    for classifier in to_write.keys():
                        no_files[to_write[classifier]]+=1
                        with open("data/{0}/{1}0{2}.json".format(classifier, to_write[classifier], no_files[to_write[classifier]]), "wb") as new_f:
                            new_f.write(json.dumps(item))
                    n+=1
                if n == len(items): self.main_menu()
                
        
    
    #Review the data for one classifier
    def review_classifier_data(self, classifier_name):
        self.classifier_status(classifier_name)
        choices = {}
        prompt = "What would you like to do?\n"
        for i, data_set in enumerate(self.status.classifiers[classifier_name]['unreviewed']):
            prompt += '{0}. Classify data in: "{1}"\n'.format(i, data_set)
            choices[i] = data_set
        prompt += '{0}. Quit\n'.format(i+1)
        choice = int(raw_input(prompt))
        cont_work = True
        while cont_work:        
            if choice < len(self.status.classifiers.keys()):
                self.review_file([classifier_name], choices[choice])
            elif choice == i+1:
                cont_work = False
    
    #Review the data for multiple classifiers at once
    def review_classifiers_data(self, classifier_names):
        choices = {}
        prompt = "What would you like to do?\n"
        i = 0
        for classifier in classifier_names:
            if self.status.classifiers[classifier]['info']['unreviewed'] > 0:
                for data_set in self.status.classifiers[classifier]["unreviewed"]:
                    prompt += '{0}. Classify data in: "{1}"\n'.format(i, data_set)
                    choices[i] = data_set
                    i+= 1
        prompt += "{0}. Continue review of a file at a position\n".format(i+1)
        prompt += '{0}. Quit\n'.format(i+2)
        cont_work = True
        while cont_work:
            choice = int(raw_input(prompt))        
            if choice <= i:
                self.review_file(classifier_names, choices[choice])
            elif choice == i+1:
                dchoice = int(raw_input("Input number of file from above"))
                fchoice = int(raw_input("Input item number to resume review at"))
                self.review_file(classifier_names, choices[dchoice], fchoice)
            elif choice == i+2:
                cont_work = False
    
    
    def classifier_menu(self, classifier_name):
        
        cont_work = True
        settings = self.status.classifiers[classifier_name]['info']['settings']
        while cont_work:
            self.status.classifier_status(classifier_name)
            if settings == False: print "You MUST add a settings file to continue"
            prompt = "0. Create settings file\n1. Review {0} unreviewed data files\n2. Test classifier\n3. Return to main menu".format(self.status.classifiers[classifier_name]['info']['unreviewed'])
            choice = int(raw_input(prompt))
            if choice==0:
                self.make_classifier_settings(classifier_name)
            elif choice == 1 and settings:
                self.review_classifier_data(classifier_name)
            elif choice == 2 and settings:
                self.test_classifier(classifier_name)
            elif choice == 3:
                cont_work = False
    
    def create_classifier(self):
        cont_menu = True
        while cont_menu:
            classifier_name = raw_input("Please input the name for the classifier").lower().strip()
            if not re.search(r'^[_a-zA-Z]\w*$', classifier_name):
                print 'Error: Classifier names must begin with a letter and contain only\n' \
                    'letters, numbers and underscores'
            elif exists(os.getcwd() + os.sep + "data" +os.sep + classifier_name):
                print "Error: {0} already exists".format(classifier_name)
            else:
                cont_menu = False
        moduletpl = join(TEMPLATES_PATH, 'classifier')
        copytree(moduletpl, join(CLASSIFIERS_PATH, classifier_name), ignore=IGNORE)
        for paths in TEMPLATES_TO_RENDER:
            path = join(*paths)
            tplfile = join(CLASSIFIERS_PATH,
                string.Template(path).substitute(classifier_name=classifier_name))
            print tplfile
            render_templatefile(tplfile, classifier_name=classifier_name,
                ClassifierName=string_camelcase(classifier_name))
        self.status.classifiers[classifier_name] = {}
        self.status.classifiers[classifier_name]['info'] = {"reviewed": 0, "unreviewed" : 0, 
            "settings" : 0, "features" : False}
        self.make_classifier_settings(classifier_name)
        
    def main_menu(self):
        cont_prog = 1
        #Main menu
        while cont_prog == 1:
            self.status.program_status()
            choice = -1
            choices = {}
            prompt = "What would you like to do?\n"
            for i, classifier in enumerate(self.status.classifiers.keys()):
                prompt += '{0}. Work with classifier: "{1}"\n'.format(i, classifier)
                choices[i] = classifier
            prompt += '{0}. Classify unreviewed data with all classifiers\n'.format(i+1)
            prompt += '{0}. Create new classifier\n'.format(i+2)    
            prompt += '{0}. Quit\n'.format(i+3)
            choice = int(raw_input(prompt))
            if choice < len(self.status.classifiers.keys()):
                self.classifier_menu(choices[choice])
                cont_generate = 1
            elif choice == i+1:
                self.review_classifiers_data(self.status.classifiers.keys())
                cont_prog = 1
            elif choice == i+2:
                self.create_classifier()
            elif choice == i+3:
                sys.exit(0)
            
if __name__ == '__main__':
    Manager()
