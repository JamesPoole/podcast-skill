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

import feedparser
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
        self.listen_url = ""

    def initialize(self):
        play_podcast_intent = IntentBuilder("PlayPodcastIntent").require(
            "PlayPodcastKeyword").build()
        self.register_intent(play_podcast_intent, self.handle_play_podcast_intent)

        new_episode_intent = IntentBuilder("NewEpisodeIntent").require(
            "NewEpisodeKeyword").build()
        self.register_intent(new_episode_intent, self.handle_new_episode_intent)

        if AudioService:
            self.audioservice = AudioService(self.emitter)

    def handle_play_podcast_intent(self, message):
        utter = message.data['utterance']

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]

        self.listen_url = ""
        for i in range(0, len(podcast_names)):
            if podcast_names[i] == "":
               continue
            if podcast_names[i].lower() in utter.lower():
                self.listen_url = podcast_urls[i]
        
        #return false if Mycroft could not hear the name of the podcast
        if self.listen_url == "":
            self.speak_dialog('nomatch')
            return False

        self.speak_dialog('latest')
        time.sleep(3)
        
        #parse the feed URL
        data = feedparser.parse(self.listen_url)

        try:
            episode = (data["entries"][0]["media_content"][0]["url"])
        except:
            episode = (data['entries'][0]['links'][1]['href'])

        episode_title = (data['entries'][0]['title'])
        # if audio service module is available use it
        if self.audioservice:
            self.audioservice.play(episode)
        else: # othervice use normal mp3 playback
            self.process = play_mp3(episode)



        self.enclosure.mouth_text(episode_title)

    def handle_new_episode_intent(self, message):
        utter = message.data['utterance']
        json_path = join(self._dir, "latest_check.json")
        with open(json_path, 'r') as read_file:
            last_check = json.load(read_file)

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]

        #check if there are new episodes compared to the last check
        new_episodes = []
        for i in range(0, len(podcast_urls)):
            if not podcast_urls[i]:
                continue
            data = feedparser.parse(podcast_urls[i])
            last_episode = (data['entries'][0]['title'])

            if last_check["latest_episodes"][i] != last_episode:
                last_check["latest_episodes"][i] = last_episode
                new_episodes.append(i)

        #if the new episode list is empty, there are no new episodes
        if len(new_episodes) == 0:
            speech_string = "There are no new episodes of your favourite podcasts"
        else:
            #create the string for mycroft to say
            speech_string = "There are new episodes of "

            for i in range(0, len(new_episodes)):
                #if the podcast is the last in a list add "and" before the podcast name
                if i == (len(new_episodes)-1) and i > 0:
                    speech_string = speech_string + "and " + podcast_names[new_episodes[i]] + " "
                else:
                    speech_string = speech_string + podcast_names[new_episodes[i]] + ", "

            #update the latest check file
            with open(join(self._dir, "latest_check.json"), 'w') as write_file:
                json.dump(last_check, write_file)

        self.speak(speech_string)

    def stop(self):
        pass

def create_skill():
    return PodcastSkill()
