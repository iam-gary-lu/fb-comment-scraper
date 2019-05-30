import webapp2
import os
import jinja2
from google.appengine.ext import ndb
from google.appengine.ext import db
from google.appengine.api import memcache
import logging 
import group_db
import deferred_functions
import json
from urlparse import parse_qs
from urlparse import urlparse
from google.appengine.api import urlfetch
#import prawcore #receiving an import error after updating gae...
import praw
from google.appengine.ext import deferred
from google.appengine.runtime import DeadlineExceededError
import requests
from requests_toolbelt.adapters import appengine
appengine.monkeypatch()
try:
    from urllib.request import urlopen, Request, HTTPError
except ImportError:
    from urllib2 import urlopen, Request, HTTPError

from datetime import datetime, timedelta, date
from apiclient import discovery
from oauth2client import client, crypt


JINJA_ENVIRONMENT = jinja2.Environment(
	loader = jinja2.FileSystemLoader(os.path.dirname(__file__)),
		extensions = ['jinja2.ext.autoescape'],
		autoescape = True)


nytimes_api_key = '***************'
nytimes_api_key_alt = '**************'

reddit_user_agent = '************'
reddit_client_id = '**************'
reddit_client_secret = '****************'

app_id = "******************"
app_secret = "******************"  
fb_api_key = app_id + "|" + app_secret

test_url = 'https://mville-insights-test.appspot.com'
dev_url = 'http://localhost:8080'

breitbart_page_id = '95475020353'
huffpost_page_id = '18468761129'

google_OAuth_client_ID = '*********************'
google_OAuth_client_secret = '*********************'

MEMCACHE_POSTS_LIST= 'posts_to_classify'
ACTIVE_CLASSIFICATION = 'current_classification'

class home(webapp2.RequestHandler):
	def get(self):
		urlfetch.set_default_fetch_deadline(60)
		breitbart_page_id = '95475020353'
		huffpost_page_id = '18468761129'
		huffpost_query = group_db.fb_post.query(group_db.fb_post.fb_page_id == huffpost_page_id)
		huffpost_post_num = huffpost_query.count()
		breitbart_query = group_db.fb_post.query(group_db.fb_post.fb_page_id == breitbart_page_id)
		breitbart_post_num = breitbart_query.count()

		logging.info('num of breitbart posts: '+str(breitbart_post_num))
		logging.info('num of huffpost posts: '+str(huffpost_post_num))

		earliest_date = datetime.strptime('01/01/2016', '%m/%d/%Y')
		fb_q = group_db.fb_post.query(group_db.fb_post.fb_post_timestamp >= earliest_date)
		post_num_since_last_year = fb_q.count()

		logging.info('num posts since 2016: '+str(post_num_since_last_year))

		huffpost_2016_posts_q = group_db.fb_post.query(group_db.fb_post.fb_page_id == huffpost_page_id, group_db.fb_post.fb_post_timestamp >=earliest_date )
		breitbart_2016_posts_q = group_db.fb_post.query(group_db.fb_post.fb_page_id == breitbart_page_id, group_db.fb_post.fb_post_timestamp >=earliest_date )
		huffpost_post_num_2016 = huffpost_2016_posts_q.count()
		breitbart_post_num_2016 = breitbart_2016_posts_q.count()


		logging.info('num of huffpost posts since 2016: '+str(huffpost_post_num_2016))
		logging.info('num of breitbart posts since 2016: '+str(breitbart_post_num_2016))

		#below query is too large, taking it out for now
		#comment_size_q = group_db.comment.query()
		#comment_num= len(comment_size_q.fetch(keys_only=True))
		#logging.info('num of comments is : '+str(comment_num))

		obj = {'BB post total': breitbart_post_num, 'HP post total': huffpost_post_num, 'BB posts since 2016': breitbart_post_num_2016, 'HP posts since 2016': huffpost_post_num_2016}
		self.response.out.write(json.dumps(obj))

#use for debugging or low volume token verification
def is_valid(token):
	url = 'https://www.googleapis.com/oauth2/v3/tokeninfo'
	r = requests.get(url,params={'id_token':token})

	if r.status_code == requests.codes.ok:
		return True

	else:
		return False


#expects question, scheme_id, human_reviewed params
class Create_Classification(webapp2.RequestHandler):
	def post(self):
		question = self.request.get('question')
		scheme_id = self.request.get('scheme_id')
		human_reviewed = self.request.get('human_reviewed')

		if not question and scheme_id and human_reviewed:
			self.response('missing parameter. Looking for following params: question, scheme_id, human_reviewed')

		else:
			classification = group_db.classification(classification_choices = ['Yes', 'No', 'Neither'],
													 question = question, scheme_id = scheme_id, human_classification = human_reviewed)
			key = classification.put()
			logging.info('created new classification w/ scheme: '+scheme_id)
			self.response('created new classification w/ scheme: '+scheme_id)



class Validate(webapp2.RequestHandler):
	def post(self):
		token = self.request.get('idtoken')
		try:
			idinfo = client.verify_id_token(token, google_OAuth_client_ID )
			if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
				raise crypt.AppIdentityError('wrong issuer.')

		except crypt.AppIdentityError:
			logging.info('token invalid')
			self.response.set_status(403,'invalid token')



		userid = idinfo['sub']
		logging.info('login successful! Redirecting to tagging')
		self.redirect('/tagging', body={'id':userid})


class Setting(webapp2.RequestHandler):
	def post(self): #expects following params. action:['create','set'], name, value
		action = self.request.get('action')
		setting_name = self.request.get('name')
		setting_value = self.request.get('value') #assuming value is a urlsafe key
		if not action or not setting_name or not setting_value:
			self.response.write('missing at least one of following params: action, setting_name, setting_value')
			logging.info('missing at least one of following params: action, setting_name, setting_value')
			return

		settings_q = group_db.setting.query(group_db.setting.name == setting_name)
		if action == 'create':
			if settings_q.count() >= 1:
				self.response.write('found existing setting with name already. Use set on action param')
				logging.info('found existing setting with name already. Use set on action param')
				return
			try:
				value_key = ndb.Key(urlsafe = setting_value)
				setting = group_db.setting(name=setting_name, value=value_key)
				setting_key = setting.put()
				logging.info('created new setting: ' + str(setting_key.urlsafe()))

			except db.BadPropertyError, db.BadRequestError:
				self.response.write('bad key given')
				logging.info('bad key given')
				return

		if action == 'set':
			if settings_q.count() == 0:
				self.response.write('no existing setting with given name. Use create on action param')
				logging.info('no existing setting with given name. Use create on action param')
				return
			try:
				value_key = ndb.Key(urlsafe = setting_value)
				setting = settings_q.get()
				setting.value = value_key
				key = setting.put()
				self.response.write('updated setting: ' + str(key.urlfsafe()))
				logging.info('updated setting: ' + str(key.urlfsafe()))

			except db.BadPropertyError, db.BadRequestError:
				self.response.write('bad key given')
				logging.info('bad key given')
				return



		#TODO: write delete method for settings
		if action == 'delete':
			self.response.write('delete method not written yet!')
			logging.info('delete method not written yet!')

		else:
			self.response.write('provided unknown action for settings')
			logging.info('provided unknown action for settings')


#TODO Prob want to make this selection criteria smarter in the future
def generate_posts_for_classification():
	posts_q = group_db.fb_post.query()
	posts_q.order(-group_db.fb_post.num_comments_ds)
	results = posts_q.fetch(projection=[group_db.fb_post.fb_post_id], limit = 100)


	existing_list = memcache.get(MEMCACHE_POSTS_LIST)
	if existing_list:
		memcache.set(MEMCACHE_POSTS_LIST, results)
	else:
		memcache.add(MEMCACHE_POSTS_LIST, results)







class Prep_Tagging(webapp2.RequestHandler):
	def post(self):
		setting_q = group_db.setting.query(group_db.setting.name == ACTIVE_CLASSIFICATION)
		result = setting_q.fetch()
		if len(result) != 1:
			self.response.write('incorrect number of settings named current_classification. Should only be 1')
			logging.info('incorrect number of settings named current_classification. Should only be 1')
			return

		deferred.defer(generate_posts_for_classification)



class Signin(webapp2.RequestHandler):
	def get(self):
		#TODO write get	handler

class Tagging(webapp2.RequestHandler):
	def get(self):
		# TODO: fill in here

		id = self.request.get('id')
		if not id: #Is this the write way to check for signed in user?
			self.redirect('/signin')

		posts_list = memcache.get(MEMCACHE_POSTS_LIST)
		if not posts_list:
			generate_posts_for_classification()

		#TODO: Find better way to pick comments for tagging
		true_flag = True
		while true_flag:
			for post in posts_list:
				comment_q = group_db.comment.query(ndb.AND(group_db.comment.source_parent_post_id == post.fb_post_id, group_db.comment.source_parent_comment_id == None))
				comment_q.order(-group_db.comment.total_reaction)










	def post(self):


		# TODO: fill in here



#ToDo: Rewrite in future, currently doesn't do anything. Original functionality taken over by getComments handler
class update(webapp2.RequestHandler):
	def post(self):
		#self.update_nytimes()
		self.update_fbposts()
		logging.info('updated!')

	def update_nytimes(self): #helper for interfacing with nytimes API
		#just updating fb_posts containing nytimes links (for now)
		current_records = group_db.fb_post.query(group_db.fb_post.link_type == 'link').fetch()
		for post in current_records:
			logging.info('iterating through posts')



class get_fb_posts(webapp2.RequestHandler):
	def post(self):
		fb_page_id = self.request.get('fb_id')
		since_date = self.request.get('since_date')  # must be in form Y-M-D
		until_date = self.request.get('until_date')
		debug_flag = self.request.get('debug')
		fb_base_url = 'https://graph.facebook.com/v2.9/'
		fb_access_token = fb_api_key

		if since_date and until_date:  # if true, just get posts between given dates
			if debug_flag:
				deferred.defer(get_fb_posts_since, since_date, until_date, fb_page_id, fb_api_key, _queue='debugQ')
				return
			deferred.defer(get_fb_posts_since, since_date, until_date, fb_page_id, fb_api_key, _queue='fbPostQ')
			return
		else:
			self.response.out.write({'message': 'need to include since_date and until_date in Y-M-D format '})
			return

		# ToDO Rewrite below code
		# how to optimize this query? look into genericProperty
		#current_posts = group_db.fb_post.query()
		#current_posts.filter(ndb.GenericProperty('fb_page_id') == fb_page_id)
		#current_posts.order(-group_db.fb_post.fb_post_timestamp)
		#results = current_posts.fetch(1)
		#if results:
		#	latest_post = results[0]
		#	# call update helper to look for new posts
		#	fb_post_id = latest_post.fb_post_id
		#	if req.status_code == requests.codes.ok:
		#		get_all_fb_posts(fb_page_id, fb_api_key, **{'latest_fb_post_id': fb_post_id})
		#	else:
		#		# TODO make this branch smarter in the future
		#		logging.info('could not find fbpost from api!')
		#		return
		#else:
			# call helper to get all posts from this page
		#	get_all_fb_posts(fb_page_id, fb_api_key)

def get_fb_posts_since(start_date, until_date, page_id, fb_key):
	url = deferred_functions.get_fb_feed_url_builder(page_id, fb_key, **{'since': start_date, 'until': until_date})
	logging.info('sectioned post feed url is: '+url)
	deferred_functions.get_all_fb_posts(page_id, fb_key, url)


class getComments(webapp2.RequestHandler):
	def post(self):
		earliest_date = datetime.strptime('01/01/2016', '%m/%d/%Y')
		debug_flag = self.request.get('debug')
		load_test_flag = self.request.get('load_test')
		if debug_flag:
			logging.info('found debug flag, setting earliest time to: 7/25/17')
			earliest_date = datetime.strptime('07/25/2017', '%m/%d/%Y')
		fb_q = group_db.fb_post.query(group_db.fb_post.fb_post_timestamp >= earliest_date, projection=[group_db.fb_post.fb_post_id])
		if load_test_flag:
			logging.info('load_test flag is up, creating query of 1000 posts for comment scraping')
			fb_q = group_db.fb_post.query(projection=[group_db.fb_post.fb_post_id]).order(-group_db.fb_post.comment_diff)

		old_c = None
		more = True
		count_so_far = 0
		while more:
			count_so_far = count_so_far + 50
			posts, next_cursor, more = fb_q.fetch_page(50, start_cursor=old_c)
			for post in posts:
				logging.info('pushing:' + str(post.fb_post_id) + 'to push queue')
				if debug_flag:
					deferred.defer(deferred_functions.get_fb_comments, post.fb_post_id, fb_api_key, _queue='debugQ')

				else:
					deferred.defer(deferred_functions.get_fb_comments, post.fb_post_id, fb_api_key, _queue='fbCommentsQ')
			old_c = next_cursor
			if load_test_flag and count_so_far >= 75:
				logging.info('load_test flag is up and count >= 100, ending function')
				break


class Find_dup(webapp2.RequestHandler):
	def post(self):
		logging.info('looking for duplicates')
		#deferred.defer(find_dup, None, None, None, _queue = "removeDupQ")
		#splitting up query space by post time
		latest_entry = group_db.fb_post.query(projection=[group_db.fb_post.fb_post_timestamp]).order(-group_db.fb_post.fb_post_timestamp).fetch(1)
		earliest_entry = group_db.fb_post.query(projection=[group_db.fb_post.fb_post_timestamp]).order(group_db.fb_post.fb_post_timestamp).fetch(1)
		logging.info ('latest_date is : '+str(latest_entry[0].fb_post_timestamp))
		logging.info('earliest date is: '+str(earliest_entry[0].fb_post_timestamp))

		obj={'latest_date is' :str(latest_entry[0].fb_post_timestamp), 'earliest date is':str(earliest_entry[0].fb_post_timestamp)}
		self.response.write(json.dumps(obj))
		time_delta = (latest_entry[0].fb_post_timestamp - earliest_entry[0].fb_post_timestamp).total_seconds() / 1000
		logging.info('time_delta is: '+str(time_delta))


		earliest_dt = earliest_entry[0].fb_post_timestamp
		latest_dt = latest_entry[0].fb_post_timestamp
		cur_dt = earliest_dt


		while cur_dt < latest_dt:
			nxt_dt = cur_dt + timedelta(seconds = time_delta)
			if nxt_dt > latest_dt:
				nxt_dt = latest_dt
			deferred.defer(find_dup_TEST, cur_dt, nxt_dt, _queue = 'removeDupQ' )
			cur_dt = nxt_dt


#Use this instead of find_dup() below
def find_dup_TEST(earliest_dt, latest_dt):
	post_q = group_db.fb_post.query(group_db.fb_post.fb_post_timestamp >= earliest_dt, group_db.fb_post.fb_post_timestamp <= latest_dt)
	logging.info('num in query is: '+str(post_q.count()))


	more = True
	cursor = None
	dup_dict = {}
	try:
		while more:
			posts, next_cursor, more = post_q.fetch_page(100, start_cursor=cursor, projection=[group_db.fb_post.fb_post_id])
			logging.info('total duplicates so far is: ' + str(len(dup_dict)))
			for post in posts:
				post_key = str(post.key)
				post_fb_id = post.fb_post_id
				dup_num = group_db.fb_post.query(group_db.fb_post.fb_post_id == post_fb_id).count()
				if dup_num > 1:
					dup_dict[post_fb_id] = dup_num - 1
					logging.info('duplicate post found for : ' + post_fb_id + ' , found ' + str(dup_num - 1) + 'x')
				cursor = next_cursor
				if len(dup_dict) > 500:
					total = 0
					for dup in dup_dict:
						total = total + dup_dict[dup]
					duplicates = group_db.duplicate(duplicates=dup_dict, num_duplicates=len(dup_dict),
													total_duplicates=total)
					k = duplicates.put()
					logging.info('500 duplicate posts found, created duplicate entity: ' + str(k))
					dup_dict = {}
			if more:
				logging.info('looking at next page of results: ' + str(next_cursor))
				cursor = next_cursor

			# deferred.defer(find_dup, next_cursor, post_q, dup_dict, _queue = 'removeDupQ' )
			# return
			else:
				more = False
		if len(dup_dict) > 0:
			total = 0
			for dup in dup_dict:
				total = total + dup_dict[dup]
			dup = group_db.duplicate(duplicates=dup_dict, num_duplicates=len(dup_dict), total_duplicates=total)
			key = dup.put()
			logging.info('created duplicate entity: ' + str(key))
		logging.info('finished checking for duplicate posts!')
		return
	except DeadlineExceededError:
		logging.info('hit deadlineExceededError')
		deferred.defer(find_dup_TEST, cursor, post_q, dup_dict, _queue='removeDupQ')
		return


#seems to be generating false positives somewhere...Replace this with find_dup_TEST
def find_dup(ext_cursor, ext_query, ext_dups): #find and returns duplicate fb ids for posts and comments
	cursor = None
	if ext_cursor:
		cursor = ext_cursor
	post_q = group_db.fb_post.query()
	if ext_query:
		post_q = ext_query
	dup_dict = {}
	if ext_dups:
		dup_dict = ext_dups
	more = True
	try:
		while more:
			posts, next_cursor, more = post_q.fetch_page(100, start_cursor=cursor)
			logging.info('total duplicates so far is: '+str(len(dup_dict)))
			for post in posts:
				post_key = str(post.key)
				post_fb_id = post.fb_post_id
				dup_num = group_db.fb_post.query(group_db.fb_post.fb_post_id == post_fb_id).count()
				if dup_num > 1:
					dup_dict[post_fb_id] = dup_num-1
					logging.info('duplicate post found for : '+post_fb_id+ ' , found '+str(dup_num-1)+'x')
				cursor = next_cursor
				if len(dup_dict) >500:
					total = 0
					for dup in dup_dict:
						total = total + dup_dict[dup]
					duplicates = group_db.duplicate(duplicates = dup_dict, num_duplicates = len(dup_dict), total_duplicates = total)
					k = duplicates.put()
					logging.info('500 duplicate posts found, created duplicate entity: '+str(k))
					dup_dict={}
			if more:
				logging.info('looking at next page of results: '+str(next_cursor))
				cursor = next_cursor

				#deferred.defer(find_dup, next_cursor, post_q, dup_dict, _queue = 'removeDupQ' )
				#return
			else:
				more = False
		if len(dup_dict) > 0:
			total = 0
			for dup in dup_dict:
				total = total + dup_dict[dup]
			dup = group_db.duplicate(duplicates = dup_dict, num_duplicates = len(dup_dict), total_duplicates = total)
			key = dup.put()
			logging.info('created duplicate entity: '+str(key))
		logging.info('finished checking for duplicate posts!')
		return
	except DeadlineExceededError:
		logging.info('hit deadlineExceededError')
		deferred.defer(find_dup, cursor, post_q, dup_dict, _queue = 'removeDupQ' )
		return


class Delete_dup(webapp2.RequestHandler):
	def post(self):
		dup_q = group_db.duplicate.query(group_db.duplicate.addressed == False)
		if dup_q.count() > 0:
			logging.info('found existing dups')
			deferred.defer(init_dup_rmv, dup_q, _queue = 'removeDupQ')


def init_dup_rmv(ext_query):
	query = ext_query
	duplicates = query.fetch()
	for dup in duplicates:
		deferred.defer(rmv_dup, dup.key, _queue = "removeDupQ")
	return


def rmv_dup(dup_key):
	key = dup_key
	dup = key.get()
	dup_dict = dup.duplicates
	repeats_key_list=[]
	for fb_id in dup_dict:
		repeated_posts_q = group_db.fb_post.query(group_db.fb_post.fb_post_id == fb_id)
		ordered_q = repeated_posts_q.order(-group_db.fb_post.num_comments)
		if ordered_q.count() == 1:
			logging.info('found an entity that is not a duplicate: '+ str(ordered_q.fetch()[0].key.urlsafe())+'...moving on')
			pass
		repeat_keys = ordered_q.fetch(offset=1, keys_only = True)
		repeats_key_list.extend(repeat_keys)
	ndb.delete_multi(repeats_key_list)
	logging.info('deleted '+str(len(repeats_key_list))+ ' repeated entities')
	return


class update_duplicate_schema(webapp2.RequestHandler):
	def post(self):
		dup_q = group_db.duplicate.query()
		results = dup_q.fetch()
		for dup in results:
			dup.addressed = False
			dup.put()
		logging.info('finished adding')

#Todo: consolidate this code with find_dup() later. Both are setting up to query over all posts
class update_post_schema(webapp2.RequestHandler):
	def post(self):

		# splitting up query space by post time
		latest_entry = group_db.fb_post.query(projection=[group_db.fb_post.fb_post_timestamp]).order(-group_db.fb_post.fb_post_timestamp).fetch(1)
		earliest_entry = group_db.fb_post.query(projection=[group_db.fb_post.fb_post_timestamp]).order(group_db.fb_post.fb_post_timestamp).fetch(1)
		logging.info('latest_date is : ' + str(latest_entry[0].fb_post_timestamp))
		logging.info('earliest date is: ' + str(earliest_entry[0].fb_post_timestamp))

		time_delta = (latest_entry[0].fb_post_timestamp - earliest_entry[0].fb_post_timestamp).total_seconds() / 1000

		earliest_dt = earliest_entry[0].fb_post_timestamp
		latest_dt = latest_entry[0].fb_post_timestamp
		cur_dt = earliest_dt

		while cur_dt < latest_dt:
			nxt_dt = cur_dt + timedelta(seconds=time_delta)
			if nxt_dt > latest_dt:
				nxt_dt = latest_dt
			deferred.defer(update_fbpost_schema, cur_dt, nxt_dt, _queue='postMaintQ')
			cur_dt = nxt_dt


def update_fbpost_schema(earliest_dt, latest_dt):
	post_q = group_db.fb_post.query(group_db.fb_post.fb_post_timestamp >= earliest_dt,
									group_db.fb_post.fb_post_timestamp <= latest_dt,)
	logging.info('num in query is: ' + str(post_q.count()))

	more = True
	cursor = None

	try:
		while more:
			posts, next_cursor, more = post_q.fetch_page(100, start_cursor=cursor)
			for post in posts:
				post_fb_id = post.fb_post_id
				comment_ds_num = group_db.comment.query(group_db.comment.source_parent_post_id == post_fb_id).count()
				post.num_comments_ds = comment_ds_num
				post.put()
				cursor = next_cursor
			if more:
				logging.info('looking at next page of results: ' + str(next_cursor))
				cursor = next_cursor
			else:
				more = False

		logging.info('updated schema!')
		return
	except DeadlineExceededError:
		logging.info('hit deadlineExceededError')
		deferred.defer(find_dup, cursor, post_q, _queue='postMaintQ')
		return


#ToDo: Rewrite into more robust resume handler that can try to resume error entities
class Resume(webapp2.RequestHandler):
	def post(self):
		type = self.request.get('type')
		url = self.request.get('resume_url')
		fb_obj_id = self.request.get('fb_obj_id')

		url_pieces = urlparse(url)

		after_param = parse_qs(url_pieces.query)['after'][0]
		logging.info ('after param from url is: '+after_param)

		if type == 'posts':
			logging.info ('resuming fb post colllection with: '+url)
			deferred.defer(deferred_functions.get_all_fb_posts, fb_obj_id, fb_api_key, url, **{'after': after_param})

		if type == 'comments':
			logging.info('resuming fb comments collection with: '+url)
			deferred.defer()


class Get_missing_post_data(webapp2.RequestHandler):
	def post(self):
		post_q = group_db.fb_post.query(group_db.fb_post.num_comments == None)
		missing_comment_ds = group_db.fb_post.query(group_db.fb_post.num_comments_ds == None)
		missing_comment_ds_count = missing_comment_ds.count()
		missing_num = post_q.count()
		obj = {'missing records': missing_num, 'posts missing comment_ds': missing_comment_ds_count}
		self.response.write(json.dumps(obj))
		if missing_num > 0:
			cursor = None
			more = True
			while more:
				posts_k, next_cursor, more = post_q.fetch_page(100, start_cursor=cursor, keys_only=True)
				deferred.defer(get_fbpost_data, posts_k, _queue='postMaintQ')
				cursor = next_cursor


#TODO: batch this request for multiple fb post ids in the future
def get_fbpost_data(posts_key_list):
	for key in posts_key_list:
		post = key.get()
		fb_post_id = post.fb_post_id
		url = deferred_functions.fb_post_url_builder(fb_post_id, fb_api_key)
		try:
			r = requests.get(url)
			logging.info('resp is : '+json.dumps(r.json()))
			if 'error' in r.json():
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
						continue
				error = group_db.error(url=r.url, fb_entity=fb_id, type='FB_POST')
				error.timestamp.append(now)
				error_key = error.put()
				logging.info('created new error entity: ' + str(error_key))
				continue
			data = r.json()
			entity_params = deferred_functions.process_entity_params(data, 'post')
			post.populate(**entity_params)
			post.put()
		except DeadlineExceededError:
			logging.info('got DeadlineExceededError')
			url_pieces = urlparse(r.url)
			fb_id = url_pieces.path.replace('/v2.9/', '')
			existing_error = group_db.error.query(group_db.error.fb_entity == fb_id).fetch(keys_only=True)
			now = datetime.now()
			if existing_error:
				try:
					ext_error = existing_error[0].get()
					ext_error.timestamp = ext_error.timestamp.append(now)
					ext_error.count = ext_error.count+1
					key = ext_error.put()
					logging.info('updated existing error: ' + key.urlfsafe())
				except db.BadValueError:
					logging.info('ran into old entity property definition, moving on...')
					continue
			else:
				error = group_db.error(url=r.url, entity=fb_id, type='FB_POST')
				error.timestamp.append(now)
				error_key = error.put()
				logging.info('created new error entity: ' + error_key.urlsafe())
			continue
	logging.info('finished updating missing posts!')





class ScrapeDailyPosts(webapp2.RequestHandler):
	def get(self):
		today = datetime.today()
		time_diff = timedelta(hours=24)
		today_str = today.strftime('%Y-%m-%d')
		yesterday = today - time_diff
		yesterday_str = yesterday.strftime('%Y-%m-%d')

		logging.info('today str is: '+today_str)
		logging.info('yesterday str is: '+yesterday_str)
		deferred.defer(get_fb_posts_since, yesterday_str, today_str, huffpost_page_id, fb_api_key)
		deferred.defer(get_fb_posts_since, yesterday_str, today_str, breitbart_page_id, fb_api_key)
		self.response.write(json.dumps({'today str':today_str, 'yesterday str':yesterday_str}))
		self.response.set_status(200)



class ScrapeDailyComments(webapp2.RequestHandler):
	def get(self):
		today = datetime.now()
		temp_start_date =  today.replace(day=26)
		start_date = today.replace(hour=0,minute=0,second=0,microsecond=0)
		end_date = today.replace(hour=23,minute=59,second=59,microsecond=999999)
		logging.info('start_date is: '+str(start_date))
		logging.info('end_date is: '+str(end_date))

		# pass a 'debug' param when you want to get comments for posts within a range based on post timestamp
		debug = self.request.get('debug')
		if debug:
			to_scrape_q = group_db.fb_post.query(ndb.AND(group_db.fb_post.fb_post_timestamp <=end_date,
												 group_db.fb_post.fb_post_timestamp >= temp_start_date),
												projection=[group_db.fb_post.fb_post_id, group_db.fb_post.ignore_count])
			logging.info('count is: '+str(to_scrape_q.count()))
			self.response.write(str(to_scrape_q.count()))
			return

		to_scrape_q = group_db.fb_post.query(ndb.AND(group_db.fb_post.nxt_comment_scrape_date <=end_date,
													 group_db.fb_post.nxt_comment_scrape_date >=start_date),
											projection=[group_db.fb_post.fb_post_id, group_db.fb_post.ignore_count])
		more = True
		old_c = None
		logging.info('number of posts prepping for comment scraping: ' + str(to_scrape_q.count()))
		while more:
			posts, next_cursor, more = to_scrape_q.fetch_page(50, start_cursor=old_c)
			for post in posts:
				if post.ignore_count >= 3:
					continue
				deferred.defer(deferred_functions.get_fb_comments, post.key, post.fb_post_id, fb_api_key, _queue='fbCommentsQ')
			old_c = next_cursor
		self.response.set_status(200)
		self.response.out.write('enqued'+str(to_scrape_q.count())+'posts for comment scraping')




#
# Misc functions written for testing purposes or not currently used
#
def test_deffered():
	reddit = praw.Reddit(user_agent=reddit_user_agent, client_id=reddit_client_id, client_secret=reddit_client_secret)
	submissions = reddit.subreddit('latestagecapitalism').hot(limit=5)
	for sub in submissions:
		logging.info(sub.title)


class reddit(webapp2.RequestHandler):
	def post(self):
		#logging.info('hello')
		#reddit = praw.Reddit(user_agent=reddit_user_agent, client_id=reddit_client_id, client_secret=reddit_client_secret)
		#submissions = reddit.subreddit('latestagecapitalism').hot(limit=5)
		#for sub in submissions:
			#logging.info(sub.title)
		deferred.defer(test_deffered, _queue='nytimesCommentsQueue')


class Test_post(webapp2.RequestHandler):
	def post(self):
		logging.info('inserting dummy duplicate post')
		post_q = group_db.fb_post.query()
		post = post_q.fetch(1)[0]

		logging.info('picked: '+post.key.urlsafe())

		b = group_db.fb_post()
		b.populate(**post.to_dict())

		cloned_key = b.put()
		logging.info('inserted clone: '+cloned_key.urlsafe())


def test_deffered():
	reddit = praw.Reddit(user_agent=reddit_user_agent, client_id=reddit_client_id,
						 client_secret=reddit_client_secret)
	submissions = reddit.subreddit('latestagecapitalism').hot(limit=5)
	for sub in submissions:
		logging.info(sub.title)


class reddit(webapp2.RequestHandler):
	def post(self):
		# logging.info('hello')
		# reddit = praw.Reddit(user_agent=reddit_user_agent, client_id=reddit_client_id, client_secret=reddit_client_secret)
		# submissions = reddit.subreddit('latestagecapitalism').hot(limit=5)
		# for sub in submissions:
		# logging.info(sub.title)
		deferred.defer(test_deffered, _queue='nytimesCommentsQueue')


###################################################################

application = webapp2.WSGIApplication([

('/getfbpost', get_fb_posts),

('/getfbcomments', getComments),

('/resume', Resume),

('/update', update), #don't use, use /getfbcomments instead

('/home', home),

('/deldup', Delete_dup),

('/finddup', Find_dup),

('/updatedup', update_duplicate_schema),

('/updatepostschema', update_post_schema),

('/testpost', Test_post),

('/missingpoststat', Get_missing_post_data),

('/cron/dailyposts', ScrapeDailyPosts ),

('/cron/dailycomments', ScrapeDailyComments),

('/dailycomments', ScrapeDailyComments),

('/validate', Validate),

('/create_classification', Create_Classification),

('/prep', Prep_Tagging),

('/tagging', Tagging),

('/setting', Setting ),

('/signin', Signin)



],debug = True)
