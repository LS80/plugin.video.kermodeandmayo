import sys
import re
import xbmc

if __name__ == '__main__':
    movie_title = re.sub(' +', '+', sys.listitem.getLabel())
    path = "plugin://plugin.video.kermodeandmayo/youtube/search/{0}".format(movie_title)
    xbmc.executebuiltin("Container.Update({0})".format(path))
