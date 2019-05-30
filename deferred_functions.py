from google.appengine.ext import ndb
from google.appengine.ext import db
import logging
import group_db
import json
import dateutil.parser as dateparser
from urlparse import urlparse
from google.appengine.api import urlfetch
#import prawcore #receiving an import error after updating gae...
import praw
from google.appengine.ext import deferred
from google.appengine.runtime import DeadlineExceededError
import handlers
import requests
from requests_toolbelt.adapters import appengine
appengine.monkeypatch()
#import requests_toolbelt.adapters.appengine
#requests_toolbelt.adapters.appengine.monkeypatch()

from google.appengine.api import taskqueue
try:
    from urllib.request import urlopen, Request, HTTPError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError

from datetime import datetime, timedelta, date


nytimes_api_key = 'ae613b3310914075acb5c90aa963f419'
nytimes_api_key_alt = '05ca2917e6314dc5a39bebb7cb804abc'

reddit_user_agent = 'python:insights_test:v1.0 (by /u/IcyAlpaca)'
reddit_client_id = 'MUGwwaJb8LBOsQ'
reddit_client_secret = 'JO4q1dFXfwGt4_jr0yApTvUyzpM'

app_id = "1873785539536922"
app_secret = "8a7ba43fa2277d8695a98d2988763fe2"  # DO NOT SHARE WITH ANYONE!
fb_api_key = app_id + "|" + app_secret

test_url = 'https://mville-insights-test.appspot.com'
dev_url = 'http://localhost:8080'

def populate_classifyQ():
	handlers.CL

def get_fb_comment_url_builder(fb_post_id, api_key, **kwargs):
	fb_base_url='https://graph.facebook.com/v2.9/'
	reaction_specifics=''
	reaction_total=''
	if 'basic' in kwargs:
		branch=fb_post_id+'?fields=comments.filter(stream).summary(true).limit(100){parent{id},created_time,from,message}'
	else:
		reaction_types = ['like', 'love', 'wow', 'haha', 'sad', 'angry', 'thankful']
		for reaction in reaction_types:
			reaction_total = 'reactions.limit(0).summary(true),'
			reaction_specifics = reaction_specifics + 'reactions.type({}).limit(0).summary(true).as({}_reaction_num)'.format(
				reaction.upper(), reaction) + ','
		branch=fb_post_id+'?fields=comments.filter(stream).summary(true).limit(100){parent{id},created_time,from,'+reaction_specifics+reaction_total+'message}'
	full_url = fb_base_url + branch + '&access_token=' + api_key
	if 'after' in kwargs:
		full_url = full_url+'&after='+kwargs['after']
	if 'since' and 'until' in kwargs:
		full_url = full_url+'&since='+kwargs['since']+'&until='+kwargs['until']

	return full_url

def get_fb_feed_url_builder(fb_obj_id, api_key, **kwargs):
	logging.info('inside fb_feed_url_builder. page id is: '+fb_obj_id)

	fb_base_url='https://graph.facebook.com/v2.9/'
	reaction_total=''
	reaction_specifics=''
	if 'basic' in kwargs:
		branch = fb_obj_id+'/posts?'

	else:
		branch=fb_obj_id+'/posts?fields=message,link,created_time,type,name,id,comments.limit(0).summary(true),shares,'
		reaction_total='reactions.limit(0).summary(true)'
		reaction_types=['like', 'love', 'wow', 'haha', 'sad', 'angry', 'thankful']
		for reaction in reaction_types:
			reaction_specifics=reaction_specifics+'reactions.type({}).limit(0).summary(true).as({}_reaction_num)'.format(reaction.upper(),reaction)+','

	full_url=fb_base_url+branch+reaction_specifics+reaction_total+'&limit=100'+'&access_token='+api_key

	if 'after' in kwargs:
		full_url = full_url+"&after="+kwargs['after']
	if 'since' in kwargs and 'until' in kwargs:
		full_url = full_url+"&since="+kwargs['since']+"&until="+kwargs['until']
	return full_url

#ToDO: consolidate code with fb feed url builder
def fb_post_url_builder(fb_post_id, api_key):

	fb_base_url = 'https://graph.facebook.com/v2.9/'
	reaction_specifics = ''
	branch = fb_post_id + '?fields=message,link,created_time,type,name,id,comments.limit(0).summary(true),shares,'
	reaction_total = 'reactions.limit(0).summary(true)'
	reaction_types = ['like', 'love', 'wow', 'haha', 'sad', 'angry', 'thankful']
	for reaction in reaction_types:
		reaction_specifics = reaction_specifics + 'reactions.type({}).limit(0).summary(true).as({}_reaction_num)'.format(
			reaction.upper(), reaction) + ','

	full_url = fb_base_url + branch + reaction_specifics + reaction_total + '&access_token=' + api_key


	return full_url

def process_entity_params(response_json, fb_type): #look for a better way to do this is the future....
	entity_values = {} #key will be entity property name, value is full mapping of value from response_json

	if 'id' in response_json:
		if fb_type == 'post':
			entity_values['fb_post_id'] = response_json['id']
		if fb_type =='comment':
			entity_values['source_comment_id'] = response_json['id']
	if 'name' in response_json:
		entity_values['post_name'] = response_json['name']
	if 'message' in response_json:
		if fb_type == 'post':
			entity_values['snippet'] = response_json['message']
		if fb_type == 'comment':
			entity_values['comment_message'] = response_json['message'] #for comments
	if 'type' in response_json:
		entity_values['link_type'] = response_json['type']
	if 'link' in response_json:
		entity_values['article_link'] = response_json['link']
	if 'created_time' in response_json:
		if fb_type =='post':
			entity_values['fb_post_timestamp'] = dateparser.parse(str(response_json['created_time'])).replace(tzinfo=None) #for posts
		if fb_type == 'comment':
			entity_values['created_timestamp'] = dateparser.parse(str(response_json['created_time'])).replace(tzinfo=None) #for comments
	if 'comments' in response_json:
		entity_values['num_comments'] = response_json['comments']['summary']['total_count']
	if 'shares' in response_json:
		entity_values['num_shares'] = response_json['shares']['count']
	if 'like_reaction_num' in response_json:
		entity_values['num_likes'] = response_json['like_reaction_num']['summary']['total_count']
	if 'love_reaction_num' in response_json:
		entity_values['num_loves'] = response_json['love_reaction_num']['summary']['total_count']
	if 'wow_reaction_num' in response_json:
		entity_values['num_wows'] = response_json['wow_reaction_num']['summary']['total_count']
	if 'haha_reaction_num' in response_json:
		entity_values['num_hahas'] = response_json['haha_reaction_num']['summary']['total_count']
	if 'sad_reaction_num' in response_json:
		entity_values['num_sads'] = response_json['sad_reaction_num']['summary']['total_count']
	if 'angry_reaction_num' in response_json:
		entity_values['num_angrys'] = response_json['angry_reaction_num']['summary']['total_count']
	if 'thankful_reaction_num' in response_json:
		entity_values['num_thankfuls'] = response_json['thankful_reaction_num']['summary']['total_count']
	if 'reactions' in response_json:
		entity_values['total_reaction'] = response_json['reactions']['summary']['total_count']

	#comment specific fields
	if 'parent' in response_json:
		entity_values['source_parent_comment_id'] = response_json['parent']['id']
	if 'from' in response_json:
		entity_values['user_id'] = response_json['from']['id']
	return entity_values

#creates Date object for a posts next scrape date
def calcNextScrapeDate(new_comments_num):
	next_date = None
	day = timedelta(days=1)
	if new_comments_num >= 300:
		next_date = datetime.now() + day
	elif new_comments_num >= 200 and new_comments_num < 300:
		next_date = datetime.now() + 2*day
	elif new_comments_num >= 150 and new_comments_num < 200:
		next_date = datetime.now() + 4*day
	elif new_comments_num >= 100 and new_comments_num < 150:
		next_date = datetime.now() + 8*day
	elif new_comments_num >= 75 and new_comments_num < 100:
		next_date = datetime.now() + 16*day
	else:
		next_date = datetime.now() + 32*day

	return next_date

def get_fb_comments(fb_obj_ndb_key, fb_obj_id, api_key, **kwargs): #assuming args[0] is full request url
	urlfetch.set_default_fetch_deadline(60)
	fb_key = api_key
	fb_parent_id = fb_obj_id
	comments_so_far = 0
	if 'comment_num_so_far' in kwargs:
		comments_so_far = kwargs['comment_num_so_far']

	entity_post_key = fb_obj_ndb_key
	fb_post = fb_obj_ndb_key.get()


	if fb_post.last_comment_scrape_date is None:

		url = get_fb_comment_url_builder(fb_obj_id, fb_key)
	else:
		#fb's api takes dates in 'Y-M-D' format
		since_date = fb_post.last_comment_scrape_date.strftime('%Y-%m-%d')
		until_date = datetime.today().strftime('%Y-%m-%d')
		url = get_fb_comment_url_builder(fb_obj_id, fb_key, **{'since':since_date,'until':until_date})






	if 'existing_url' in kwargs:#assuming kwargs['existing_ur'l is full request url
		logging.info('using existing url from api: '+kwargs['existing_url'])
		url = kwargs['existing_url']
	if 'retry_url' in kwargs:
		url = kwargs['retry_url']
	try:
		logging.info('using url for request: '+url)
		r = requests.get(url)
		#can't figure out why fb api is not returning correct data when prepending 'after' param manually, so just going to check for response type here
		if 'comments' in r.json():
			comment_list = r.json()['comments']['data']
			data_core = r.json()['comments']
			#logging.info('response is: ' + json.dumps(r.json()))
		else:
			if 'error' in r.json():
				logging.info('error response is: '+json.dumps(r.json()))
			#logging.info('response is: '+json.dumps(r.json()))
			comment_list = r.json()['data']
			data_core = r.json()
		prob_new = True
		if len(comment_list) < 3:
			sample_results = [-1] #for sake of bypassing heuristic
		else:
			sample = [comment_list[0]['id'], comment_list[len(comment_list) / 2]['id'], comment_list[-1]['id']]
			# if the first, middle, and last post in response are already in datastore, I'm assuming that all posts are already in datastore
			sample_results = group_db.comment.query(ndb.OR(group_db.comment.source_comment_id == sample[0],
														   group_db.comment.source_comment_id == sample[1],
														   group_db.comment.source_comment_id == sample[
															   2])).fetch(keys_only=True)

		if len(sample_results) == 3:
			prob_new = False
			logging.info('assuming comments exist already')

		if prob_new:
			for comment in comment_list:
				# is there a better way to check for datastore duplicates?
				existing_comment = group_db.comment.query(
					group_db.comment.source_comment_id == comment['id']).fetch(keys_only=True)
				if existing_comment:
					logging.info('comment is already in datastore')
					continue

				results = process_entity_params(comment, 'comment')
				comment_obj = group_db.comment(**results)
				comment_obj.source_parent_post_id = fb_parent_id
				comment_key = comment_obj.put()
				logging.info('created comment: ' + str(comment_key))
				comments_so_far = comments_so_far+1



		if 'paging' in data_core:
			if 'next' in data_core['paging']:
				#logging.info('found next page of results for: ' + r.url)
				#I can't figure out why manually constructing the next url is not returning the correct results, just going with facebook's next url for now
				#after_param = r.json()['comments']['paging']['cursors']['after']
				#logging.info('found after param: ' + after_param)
				#url = get_fb_comment_url_builder(fb_obj_id, fb_key, **{'after': after_param})
				logging.info('found next url: '+data_core['paging']['next'])
				url = data_core['paging']['next']
				deferred.defer(get_fb_comments, entity_post_key, fb_parent_id, fb_key, _queue='fbCommentsQ', **{'comment_num_so_far': comments_so_far, 'existing_url':url})
				return
			else:

				logging.info('no more comments, scraped comments: '+str(comments_so_far))
				if fb_post.ignore_count == None:
					fb_post.ignore_count = 0
				if comments_so_far < 50:
					fb_post.ignore_count = fb_post.ignore_count + 1
				next_scrape_date = calcNextScrapeDate(comments_so_far)
				fb_post.last_comment_scrape_date = fb_post.nxt_comment_scrape_date
				fb_post.nxt_comment_scrape_date = next_scrape_date
				fb_post.put()
				return





		else:
			logging.info('no more comments, scraped comments: ' + str(comments_so_far))

			if fb_post.ignore_count == None:
				fb_post.ignore_count == 0
			if comments_so_far < 50:
				fb_post.ignore_count = fb_post.ignore_count + 1
			next_scrape_date = calcNextScrapeDate(comments_so_far)
			fb_post.nxt_comment_scrape_date = next_scrape_date
			fb_post.put()
			return
	except DeadlineExceededError:
		logging.info('got DeadlineExceededError')
		url_pieces = urlparse(r.url)
		fb_id = url_pieces.path.replace('/v2.9/', '')
		existing_error = group_db.error.query(group_db.error.fb_entity == fb_id).fetch(keys_only=True)
		now = datetime.now()
		if existing_error:
			try:
				now = datetime.now()
				ext_error = existing_error[0].get()
				ext_error.timestamp.append(now)
				ext_error.count = ext_error.count + 1
				key = ext_error.put()
				logging.info('updated existing error: ' + key.urlfsafe())
			except db.BadValueError:
				logging.info('ran into old entity property definition, moving on...')
				pass
		error = group_db.error(url=r.url, fb_entity=fb_id, type='COMMENT')
		error.timestamp.append(now)
		error_key = error.put()
		logging.info('created new error entity: ' + str(error_key))
		return


def get_all_fb_posts(page_id, fb_key, *args, **kwargs): #args used for next url, kwargs 'after' for after_cursor value
	latest_fb_post = None
	prev_values = kwargs
	page_key = page_id
	fb_api_key = fb_key
	#if 'after' in kwargs:
		#after_value = kwargs['after']
	#taking out 'latest_fb_post_id for now
	#if 'latest_fb_post_id' in kwargs:
	#	latest_fb_post = kwargs['latest_fb_post_id']


	if args:
		logging.info('making call with existing url: '+args[0])
		url=args[0]
	else:
		url = get_fb_feed_url_builder(page_key, fb_key)
	try:
		req = requests.get(url)
		if 'error' in req.json():
			logging.info('error from api: '+json.dumps(req.json()))
		#logging.info('json from api: ' + json.dumps(req.json()))
		logging.info('request url: ' + req.url)
		post_list = req.json()['data']
		prob_new = True
		if len(post_list) < 3:
			sample_results = [-1]
		else:
			sample = [post_list[0]['id'],  post_list[len(post_list)/2]['id'], post_list[-1]['id']]
			#if the first, middle, and last post in response are already in datastore, I'm assuming that all posts are already in datastore
			sample_results = group_db.fb_post.query(ndb.OR(group_db.fb_post.fb_post_id ==sample[0],
														   group_db.fb_post.fb_post_id ==sample[1],
														   group_db.fb_post.fb_post_id == sample[2])).fetch(keys_only = True)
		if len(sample_results) == 3:
			prob_new = False #Change this back to False when dates are working correctly!
			logging.info('assuming posts exist already')
		if prob_new:
			for post in post_list:
				#logging.info(post)
				#taking out the latest check for now...
				#if post['id'] == latest_fb_post:
				#	logging.info('found latest post...stopping collection')
				#	return
				current_record = group_db.fb_post.query(group_db.fb_post.fb_post_id == post['id']).fetch(keys_only = True)
				if current_record:
					logging.info('post is already in datastore')
					continue
				post_obj = group_db.fb_post(**process_entity_params(post, 'post'))
				post_obj.fb_page_id = page_id
				key = post_obj.put()
				logging.info('created new post: '+key.urlsafe())
		if 'paging' in req.json():
			if 'next' in req.json()['paging']:
				nxt_url = str(req.json()['paging']['next'])
				logging.info('new page of results found: '+str(req.json()['paging']['next']))
				#removing latest_fb_post for debugging
				#if 'latest_fb_post_id' in kwargs:
				#	deferred.defer(get_all_fb_posts, page_key, fb_api_key,nxt_url, **{'latest_fb_post_id':kwargs['latest_fb_post_id']})
				deferred.defer(get_all_fb_posts, page_key, fb_api_key, nxt_url, _queue = 'fbPostQ')
				return
			logging.info('F3: no next page of posts found for: '+req.url)
			return
		else:
			logging.info('F4: no next page of posts found for: '+req.url)
			return
	except DeadlineExceededError:
		logging.info('got DeadlineExceededError')
		url_pieces = urlparse(url)
		fb_id = url_pieces.path.replace('/v2.9/', '')
		existing_error = group_db.error.query(group_db.error.fb_entity == fb_id).fetch(keys_only=True)
		now = datetime.now()
		if existing_error:
			try:
				now = datetime.now()
				ext_error = existing_error[0].get()
				ext_error.timestamp.append(now)
				ext_error.count = ext_error.count + 1
				key = ext_error.put()
				logging.info('updated existing error: ' + key.urlfsafe())
			except db.BadValueError:
				logging.info('ran into old entity property definition, moving on...')
				pass
		error = group_db.error(url=url, fb_entity=fb_id, type='MULTI_FB_POST')
		error.timestamp.append(now)
		error_key = error.put()
		logging.info('created new error entity: ' + str(error_key))
		return
