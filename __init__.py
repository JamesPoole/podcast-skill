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
from urllib.request import Request
import re

# from adapt.intent import IntentBuilder
from mycroft.skills.core import intent_file_handler  # , MycroftSkill
from mycroft.audio import wait_while_speaking
# from mycroft.util.log import getLogger
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
# TODO: use VLC for pause/resume/prev/next
try:
    from mycroft.skills.audioservice import AudioService
except:
    from mycroft.util import play_mp3
    AudioService = None

__author__ = 'jamespoole'


class PodcastSkill(CommonPlaySkill):
    def __init__(self):
        super(PodcastSkill, self).__init__(name="PodcastSkill")
        self.process = None
        self.audioservice = None
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11'

    def initialize(self):
        if AudioService:
            self.audioservice = AudioService(self.bus)

    def CPS_match_query_phrase(self, phrase):
        self.log.debug("phrase {}".format(phrase))
        # Not ready to play
        if not self.audioservice:
            return None

        confidence = 0.0
        data = None

        if 'podcast' in phrase.lower():
            bonus = 0.1
        else:
            bonus = 0

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]
        # TODO: fuzzy matching
        data = self.chosen_podcast(phrase, podcast_names, podcast_urls)

        if data:
            confidence = CPSMatchLevel.EXACT

        self.log.info("phrase: {} confidence: {} data: {}".format(phrase,
                                                                  confidence,
                                                                  data))
        return phrase, confidence, data

    def CPS_start(self, phrase, data):
            self.log.info("CPS_start phrase: {} data: {}".format(phrase, data))

            parsed_feed = pp.parse(data, urllib.request.urlopen(Request(data,
                            data=None, headers={'User-Agent': self.user_agent}))
                          )
            episode_title = (parsed_feed['episodes'][0]['title'])

            # try and parse the rss feed, some are incompatible
            try:
                episode = (parsed_feed["episodes"][0]["enclosures"][0]["url"])
            except:
                self.speak_dialog('badrss')

            # check for any redirects
            episode = urllib.request.urlopen(Request(episode, data=None, headers={'User-Agent': self.user_agent}))
            redirected_episode = episode.geturl()

            # convert stream to http for mpg123 compatibility
            http_episode = re.sub('https', 'http', redirected_episode)

            # if audio service module is available use it
            if self.audioservice:
                self.audioservice.play(http_episode, episode_title)
            else:  # othervice use normal mp3 playback
                self.process = play_mp3(http_episode)

    def chosen_podcast(self, utter, podcast_names, podcast_urls):
        for index, name in enumerate(podcast_names):
            # skip if podcast slot left empty
            if not name:
                continue
            if name.lower() in utter.lower():
                listen_url = podcast_urls[index]
                break
        else:
            listen_url = ""
        return listen_url

    @intent_file_handler('PlayPodcast.intent')
    def handle_play_podcast_intent(self, message):
        utter = message.data['utterance']
        self.enclosure.mouth_think()

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]

        for try_count in range(0, 2):
            listen_url = self.chosen_podcast(utter, podcast_names, podcast_urls)
            if listen_url:
                break
            utter = self.get_response('nomatch')
        else:
            self.speak_dialog('not.found')
            return False

        # normalise feed and parse it
        normalised_feed = pp.normalize_feed_url(listen_url)
        parsed_feed = pp.parse(normalised_feed, urllib.request.urlopen(Request(normalised_feed, data=None, headers={'User-Agent': self.user_agent})))

        # Check what episode the user wants
        episode_index = 0

        # This block adds functionality for the user to choose an episode
        while(True):
            episode_title = parsed_feed['episodes'][episode_index]['title']
            podcast_title = parsed_feed['title']

            data_dict = {"podcast_title": podcast_title,
                "episode_title": episode_title}

            if episode_index == 0:
                response = self.get_response('play.previous',
                    data=data_dict,
                    on_fail='please.repeat')
            else:
                response = self.get_response('play.next.previous',
                    data=data_dict,
                    on_fail='please.repeat')

            # error check
            if response is None:
                break

            if "stop" in response:
                self.speak("Operation cancelled.")
                return False
            elif "play" in response:
                break
            elif "previous" in response:
                episode_index += 1
            elif "next" in response:
                # ensure index doesnt go below zero
                if episode_index != 0:
                    episode_index -= 1

        self.speak("Playing podcast.")
        wait_while_speaking()

        # try and parse the rss feed, some are incompatible
        try:
            episode = (parsed_feed["episodes"][episode_index]["enclosures"][0]["url"])
        except:
            self.speak_dialog('badrss')

        # check for any redirects
        episode = urllib.request.urlopen(Request(episode, data=None, headers={'User-Agent': self.user_agent}))
        redirected_episode = episode.geturl()

        # convert stream to http for mpg123 compatibility
        http_episode = re.sub('https', 'http', redirected_episode)

        # if audio service module is available use it
        if self.audioservice:
            self.audioservice.play(http_episode, message.data['utterance'])
        else:  # othervice use normal mp3 playback
            self.process = play_mp3(http_episode)

        self.enclosure.mouth_text(episode_title)

    @intent_file_handler('LatestEpisode.intent')
    def handle_latest_episode_intent(self, message):
        utter = message.data['utterance']
        self.enclosure.mouth_think()

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]

        # check if the user specified a podcast to check for a new podcast
        for index, name in enumerate(podcast_names):
            # skip if podcast slot left empty
            if not name:
                continue
            if name.lower() in utter.lower():
                parsed_feed = pp.parse(podcast_urls[index],
                                urllib.request.urlopen(Request(podcast_urls[index], data=None, headers={'User-Agent': self.user_agent})))
                last_episode = (parsed_feed['episodes'][0]['title'])

                speech_string = "The latest episode of " + name + " is " + last_episode
                break
        else:
            # if no podcast names are provided, list all new episodes
            new_episodes = []
            for index, url in enumerate(podcast_urls):
                # skip if url slot left empty
                if not url:
                    continue
                parsed_feed = pp.parse(podcast_urls[index],
                                urllib.request.urlopen(Request(podcast_urls[index], data=None, headers={'User-Agent': self.user_agent})))
                last_episode = (parsed_feed['episodes'][0]['title'])
                new_episodes.append(last_episode)

            # skip if i[0] slot left empty
            elements = [": ".join(i) for i in zip(podcast_names, new_episodes) if i[0]]

            speech_string = "The latest episodes are the following: "
            speech_string += ", ".join(elements[:-2] + [" and ".join(elements[-2:])])

        self.speak(speech_string)

    def stop(self):
        if self.audioservice:
            self.audioservice.stop()
        else:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait()


def create_skill():
    return PodcastSkill()
