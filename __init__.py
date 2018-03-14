# Copyright 2016 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
import podcastparser as pp
import urllib
import requests
import time
from os.path import dirname, join
import re
import json

from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill
from mycroft.util.log import getLogger
try:
    from mycroft.skills.audioservice import AudioService
except:
    from mycroft.util import play_mp3
    AudioService = None

__author__ = 'jamespoole'

LOGGER = getLogger(__name__)

class PodcastSkill(MycroftSkill):

    # The constructor of the skill, which calls MycroftSkill's constructor
    def __init__(self):
        super(PodcastSkill, self).__init__(name="PodcastSkill")

        self.process = None
        self.audioservice = None

    def initialize(self):
        play_podcast_intent = IntentBuilder("PlayPodcastIntent").require(
            "PlayPodcastKeyword").build()
        self.register_intent(play_podcast_intent, self.handle_play_podcast_intent)

        latest_episode_intent = IntentBuilder("LatestEpisodeIntent").require(
            "LatestEpisodeKeyword").build()
        self.register_intent(latest_episode_intent, self.handle_latest_episode_intent)

        if AudioService:
            self.audioservice = AudioService(self.emitter)


    def chosen_podcast(self, utter, podcast_names, podcast_urls):
        listen_url = ""
        for i in range(0, len(podcast_names)):
            #check for empty podcast settings
            if podcast_names[i] == "":
               continue
            try:
                if podcast_names[i].lower() in utter.lower():
                   listen_url = podcast_urls[i]
            except:
                pass
        return listen_url

    def handle_play_podcast_intent(self, message):
        utter = message.data['utterance']

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]

        listen_url = self.chosen_podcast(utter, podcast_names, podcast_urls)

        #if misheard, retry and return false if Mycroft could not hear the name of the podcast
    	try_count = 0
        while (listen_url == "" and try_count < 2):
            try_count += 1
            response = self.get_response('nomatch')
            listen_url = self.chosen_podcast(response, podcast_names, podcast_urls)
            if try_count == 1 and listen_url == "":
                self.speak_dialog('not.found')
                return False

        #normalise feed and parse it
        normalised_feed = pp.normalize_feed_url(listen_url)
        parsed_feed = pp.parse(normalised_feed, urllib.urlopen(normalised_feed))

        #Check what episode the user wants
        episode_index = 0
        self.speak_dialog('latest')
        time.sleep(3)

        episode_title = (parsed_feed['episodes'][0]['title'])

        #some feeds have different formats, these two were the most common ones I found so it will try them both
        try:
            episode = (parsed_feed["episodes"][episode_index]["enclosures"][0]["url"])
        except:
            self.speak_dialog('badrss')

        #check for any redirects
        episode = urllib.urlopen(episode)
        redirected_episode = episode.geturl()

        # if audio service module is available use it
        if self.audioservice:
            self.audioservice.play(redirected_episode, message.data['utterance'])
        else: # othervice use normal mp3 playback
            self.process = play_mp3(redirected_episode)

        self.enclosure.mouth_text(episode_title)

    def handle_latest_episode_intent(self, message):
        utter = message.data['utterance']

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]

        #check if the user specified a podcast to check for a new podcast
        for i in range(0, len(podcast_names)):
            #skip if podcast slot left empty
            if podcast_names[i] == "":
                continue
            elif podcast_names[i].lower() in utter.lower():
                parsed_feed = pp.parse(podcast_urls[i], urllib.urlopen(podcast_urls[i]))
                last_episode = (parsed_feed['episodes'][0]['title'])

                speech_string = "The latest episode of " + podcast_names[i] + " is " + last_episode
                self.speak(speech_string)
                return True

        #if no podcast names are provided, list all new episodes
        new_episodes = []
        for i in range(0, len(podcast_urls)):
            if not podcast_urls[i]:
                continue
            parsed_feed = pp.parse(podcast_urls[i], urllib.urlopen(podcast_urls[i]))
            last_episode = (parsed_feed['episodes'][0]['title'])
            new_episodes.append(last_episode)

            speech_string = "The latest episodes are the following: "

            for i in range(0, len(new_episodes)):
                #if the podcast is the last in a list add "and" before the podcast name
                if i == (len(new_episodes)-1) and i > 0:
                    speech_string = speech_string + "and " + podcast_names[i] + ": " + new_episodes[i]
                else:
                    speech_string = speech_string + podcast_names[i] + ": " + new_episodes[i] + ", "

        self.speak(speech_string)

    def stop(self):
        pass

def create_skill():
    return PodcastSkill()
