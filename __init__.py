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
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from mycroft.audio.services.vlc import VlcService
from mycroft.util.parse import match_one, fuzzy_match

__author__ = 'jamespoole'


class PodcastSkill(CommonPlaySkill):
    def __init__(self):
        super(PodcastSkill, self).__init__(name="PodcastSkill")
        self.process = None
        self.user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11'
        self.mediaplayer = VlcService(config={'low_volume': 10, 'duck': True})
        self.state = 'idle'
        self.cps_id = "amzn-music"

    def initialize(self):
        self.mediaplayer.clear_list()
        # Setup handlers for playback control messages
        self.add_event('mycroft.audio.service.next', self.next)
        self.add_event('mycroft.audio.service.prev', self.previous)
        self.add_event('mycroft.audio.service.pause', self.pause)
        self.add_event('mycroft.audio.service.resume', self.resume)
        self.add_event('mycroft.audio.service.lower_volume', self.lower_volume)
        self.add_event('mycroft.audio.service.restore_volume',
                       self.restore_volume)

    def CPS_match_query_phrase(self, phrase):
        self.log.debug("phrase {}".format(phrase))
        # Not ready to play
        if not self.mediaplayer:
            return None

        data = None
        best_index = -1
        best_confidence = 0.0

        if 'podcast' in phrase.lower():
            bonus = 0.1
        else:
            bonus = 0

        podcast_names = [self.settings["nameone"], self.settings["nametwo"], self.settings["namethree"]]
        podcast_urls = [self.settings["feedone"], self.settings["feedtwo"], self.settings["feedthree"]]

        # fuzzy matching
        for index, name in enumerate(podcast_names):
            confidence = min(fuzzy_match(name.lower(), phrase.lower()) + bonus,
                             1.0)
            if confidence > best_confidence:
                best_index = index
                best_confidence = confidence
            self.log.debug("index {}, name {}, confidence {}".format(index, name, confidence))

        # check for exact match
        data = self.chosen_podcast(phrase, podcast_names, podcast_urls)

        if data:
            confidence = CPSMatchLevel.EXACT
        elif best_index >= 0:
            data = podcast_urls[best_index]
            if best_confidence > 0.9:
                confidence = CPSMatchLevel.EXACT
            elif best_confidence > 0.6:
                confidence = CPSMatchLevel.TITLE
            elif best_confidence > 0.1:
                confidence = CPSMatchLevel.CATEGORY
            else:
                confidence = CPSMatchLevel.GENERIC

        self.log.info("phrase: {} confidence: {} data: {}".format(phrase,
                                                                  confidence,
                                                                  data))
        return phrase, confidence, data

    def CPS_start(self, phrase, data):
            self.log.info("CPS_start phrase: {} data: {}".format(phrase, data))
            tracklist = []
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

            http_episode = re.sub('https', 'http', redirected_episode)
            self.log.info("http_episode: {}".format(http_episode))
            tracklist.append(http_episode)

            if self.state in ['playing', 'paused']:
                self.mediaplayer.stop()
                self.mediaplayer.clear_list()
            self.mediaplayer.add_list(tracklist)
            # self.speak(self._get_play_message(data))
            self.mediaplayer.play()
            self.state = 'playing'

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
        if self.state != 'idle':
            self.mediaplayer.stop()
            self.state = 'idle'
            return True
        else:
            return False

    def pause(self):
        if self.state == 'playing':
            self.mediaplayer.pause()
            self.state = 'paused'
            return True
        return False

    def resume(self):
        if self.state == 'paused':
            self.mediaplayer.resume()
            self.state = 'playing'
            return True
        return False

    def next(self):
        if self.state == 'playing':
            self.mediaplayer.next()
            return True
        return False

    def previous(self):
        if self.state == 'playing':
            self.mediaplayer.previous()
            return True
        return False

    def lower_volume(self):
        if self.state == 'playing':
            self.mediaplayer.lower_volume()
            return True
        return False

    def restore_volume(self):
        if self.state == 'playing':
            self.mediaplayer.restore_volume()
            return True
        return False

    def shutdown(self):
        if self.state != 'idle':
            self.mediaplayer.stop()
            self.mediaplayer.clear_list()


def create_skill():
    return PodcastSkill()
