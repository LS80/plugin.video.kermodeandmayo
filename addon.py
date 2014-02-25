# coding=utf-8
##########################################################################
#
#  Copyright 2014 Lee Smith
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
# 
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
# 
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##########################################################################

import os
import re
from urlparse import urlparse, urlunparse, urljoin
from datetime import date, timedelta
import time

from xbmcswift2 import Plugin
from bs4 import BeautifulSoup
import requests2

CLIP_HOST = "http://bbc.co.uk"
CLIP_URL_FMT = CLIP_HOST + "/programmes/b00lvdrj/clips/?page={0}"

CLIP_THUMB_SIZE_RE = re.compile("/\d{3,}x\d{3,}/")
CLIP_THUMB_WIDTH = 640
CLIP_THUMB_HEIGHT = 360

CLIP_PID_RE = re.compile("/(\w+)#")

CLIP_PLAYLIST_XML_FMT = CLIP_HOST + "/iplayer/playlist/{0}"
CLIP_XML_FMT = "http://open.live.bbc.co.uk/mediaselector/5/select/version/2.0/mediaset/pc/vpid/{0}"

SWF_URL = "http://emp.bbci.co.uk/emp/releases/smp-flash/revisions/1.8.12/1.8.12_smp.swf"

PODCAST_XML = "http://downloads.bbc.co.uk/podcasts/fivelive/kermode/rss.xml"
PODCAST_THUMB = "http://ichef.bbci.co.uk/podcasts/artwork/478/kermode.jpg"


plugin = Plugin()

def get_soup(url):
    response = requests2.get(url)
    return BeautifulSoup(response.text)
        
def clip_item(pid, title, duration_str, thumb_src):
    thumb_url = CLIP_THUMB_SIZE_RE.sub("/{0}x{1}/".format(CLIP_THUMB_WIDTH,
                                                          CLIP_THUMB_HEIGHT), thumb_src)
    
    minutes, seconds = duration_str.split(':')
    duration = timedelta(minutes=int(minutes), seconds=int(seconds))

    item = {'label': title,
            'thumbnail': thumb_url,
            'is_playable': True,
            'path': plugin.url_for('play_clip', pid=pid),
            'info': {'title': title,
                     'album': plugin.get_string(30000)
                     },
            'stream_info': {'video': {'duration': duration.seconds}
                            }
            }
        
    return item

def get_clips(soup, page):
    pages = soup.find('div', 'pagination')
    
    if not pages.find('li', 'next disabled'):
        next_page = str(page + 1)
        item = {'label': u"{0} ({1}) >>".format(plugin.get_string(30001), next_page),
                'path': plugin.url_for('clips', page=next_page)
                }
        yield item

    if page > 1:
        previous_page = str(page - 1)
        item = {'label': u"<< {0} ({1})".format(plugin.get_string(30002), previous_page),
                'path': plugin.url_for('clips', page=previous_page)
                }
        yield item
        
    for li in soup('li', content=CLIP_PID_RE):
        pid = CLIP_PID_RE.search(li['content']).group(1)
        title = li.find('span', {'property': 'dc:title'}).string
        duration_str = li.find('span', 'duration').string.split(" ")[1]
        thumb_src = li.find('span', 'depiction').img['src']
        
        yield clip_item(pid, title, duration_str, thumb_src)
        
def get_podcasts():
    soup = get_soup(PODCAST_XML)
    for podcast in soup('item'):
        title = podcast.title.string
        date_str = podcast.pubdate.string[:16]
        air_date = date(*(time.strptime(date_str, "%a, %d %b %Y")[:3]))
        
        media = podcast.find('media:content')
        
        item = {'label': title,
                'thumbnail': PODCAST_THUMB,
                'is_playable': True,
                'path': media['url'],
                'info': {'title': title,
                         'date': air_date.strftime("%d.%m.%Y"),
                         'size': int(media['filesize']),
                         'duration': int(media['duration']),
                         'album': plugin.get_string(30000)
                         },
                'properties': {'mimetype': 'audio/mpeg'},
                'stream_info': {'audio': {'codec': 'mp3',
                                          'language': 'en'}
                                }
                }

        yield item

@plugin.route('/')
def index():    
    return [{'label': plugin.get_string(30003),
             'path': plugin.url_for('podcasts')},
            {'label': plugin.get_string(30004),
             'path': plugin.url_for('clips', page='1')}]

@plugin.route('/podcasts')
def podcasts():
    return plugin.finish(get_podcasts(),
                         sort_methods=['date',
                                       'duration',
                                       'title',
                                       'size'])

@plugin.route('/clips/page/<page>')
def clips(page='1'):
    soup = get_soup(CLIP_URL_FMT.format(page))
    
    page = int(page)    
    if page > 1:
        update_listing = True
    else:
        update_listing = False

    return plugin.finish(get_clips(soup, page),
                         sort_methods=['playlist_order', 'duration', 'title'],
                         update_listing=update_listing)

@plugin.route('/clip/<pid>')
def play_clip(pid):
    xml = requests2.get(CLIP_PLAYLIST_XML_FMT.format(pid)).text
    programme = BeautifulSoup(xml, 'html.parser').find('item', kind='programme')
    vpid = programme['identifier']
    
    xml = requests2.get(CLIP_XML_FMT.format(vpid)).text
    media = BeautifulSoup(xml, 'html.parser').find('media', service='iplayer_streaming_h264_flv_high')
    connection = media.find(supplier='akamai')

    auth = connection['authstring']

    url = urlunparse((connection['protocol'], connection['server'], 'ondemand', None, auth, None))
    video_url = "{0} playpath={1}?{2} swfurl={3} swfvfy=1 timeout=180".format(url,
                                                                              connection['identifier'],
                                                                              auth,
                                                                              SWF_URL)
    return plugin.set_resolved_url(video_url)


if __name__ == '__main__':
    plugin.run()
