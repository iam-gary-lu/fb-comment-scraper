#this page consists of unused handler function for now


def get_fb_comments_OLD(fb_parent_id, api_key, *args, **kwargs):
	# optional values used for possible pagination. I'm assuming there's only 1 possible optional param (the 'after' param)
	fb_key = api_key
	fb_base_url = 'https://graph.facebook.com/v2.9/'
	# fb_post_id=fb_post.fb_post_id
	edge = '/comments'
	if args:
		payload = {'access_token': api_key, 'limit': 100, 'after': args[0]}
	else:
		payload = {'access_token': api_key, 'limit': 100}
	# req = requests.get(get_fb_comment_url_builder(fb_post_id, api_key))

	req = requests.get(fb_base_url + fb_parent_id + edge, params=payload)
	# logging.info('response is: '+json.dumps(req.json()))

	for comment in req.json()['data']:
		logging.info(dateparser.parse(str(comment['created_time'])))

		logging.info(comment['from']['id'])
		comment_obj = group_db.comment(source_comment_id=comment['id'], source_parent_post_id=fb_parent_id,
									   user_id=comment['from']['id'], comment_message=comment['message'],
									   created_timestamp=dateparser.parse(str(comment['created_time'])).replace(
										   tzinfo=None))
		comment_key = comment_obj.put()
		comment_key_fb_id = comment_key.get().source_comment_id
		deferred.defer(get_fb_comments_OLD, comment_key_fb_id,
					   fb_key)  # , _queue='fbCommentsQueueSUB') #for sub comments
	if 'paging' in req.json():
		if 'next' in req.json()['paging']:
			logging.info('found next page of results for: ' + comment_key_fb_id)
			after_token = req.json()['paging']['cursors']['after']
			deferred.defer(get_fb_comments_OLD, fb_parent_id, fb_key, after_token)  # for next page of comments


class updateOLD(webapp2.RequestHandler):
	def post(self):
		self.update_fbposts()

	def update_fbposts(self):
		fb_posts = group_db.fb_post.query().fetch()
		for post in fb_posts:
			logging.info('looking at post: ' + str(post))
			deferred.defer(get_fb_comments_OLD, post.fb_post_id, fb_api_key)


class upload(webapp2.RequestHandler):
	def post(self):
		row_data = json.loads(self.request.get('data'))
		for row in row_data:
			post_snippet = row['status_message']
			post_id = row['status_id']
			post_link_type = row['status_type']
			post_article_link = row['status_link']
			post_timestamp = datetime.strptime(row['status_published'], '%m/%d/%Y %H:%M')
			post_comments_num = int(row['num_comments'])
			post_shares_num = int(row['num_shares'])
			post_likes_num = int(row['num_likes'])
			post_loves_num = int(row['num_loves'])
			post_wows_num = int(row['num_wows'])
			post_sads_num = int(row['num_sads'])
			post_angrys_num = int(row['num_angrys'])

			fb_post = group_db.fb_post(snippet=post_snippet, fb_post_id=post_id, link_type=post_link_type
									   , article_link=post_article_link, fb_post_timestamp=post_timestamp
									   , num_comments=post_comments_num, num_shares=post_shares_num
									   , num_likes=post_likes_num, num_loves=post_loves_num, num_wows=post_wows_num
									   , num_sads=post_sads_num, num_angrys=post_angrys_num)
			key = fb_post.put()
			logging.info("key is: " + str(key))
		logging.info("complete!")


def update_check_nytimes_comments(fb_post, api_key):
	logging.info('using link: ' + fb_post.article_link)
	url_base = 'http://api.nytimes.com/svc/community/v3/user-content/url.json'
	if fb_post.link_type == 'link':  # make this smarter in future
		final_url = urllib2.urlopen(fb_post.article_link).geturl()  # for redirects
		params = {'url': final_url, 'api-key': api_key, 'offset': 0}
		url_params = urllib.urlencode(params)
		full_url = url_base + '?' + url_params
		response = json.loads(request_until_succeed(full_url, 3))
		logging.info(json.dumps(response))
		time.sleep(5)
		while response['results']['totalCommentsReturned'] > 0:
			comments = response['results']['comments']
			for comment in comments:
				# try:
				comment_obj = group_db.comment(source='nytimes', source_comment_id=str(comment['commentID']),
											   article_url=fb_post.article_link,
											   comment_message=comment['commentBody'],
											   created_timestamp=datetime.utcfromtimestamp(
												   float(comment['createDate'])),
											   trusted_Count=comment['trusted'], user_id=comment['userID'],
											   reply_Count=comment['replyCount'],
											   sharing_Count=comment['sharing'],
											   recommendation_Count=comment['recommendations'],
											   editors_Selection=comment['editorsSelection'],
											   times_People_Count=comment['timespeople'],
											   user_location=comment['userLocation']
											   )
				key = comment_obj.put()

				if comment['replies']:
					for reply in comment['replies']:  # just considering 1st lvl replys for now...
						reply_comment = group_db.comment(source='nytimes', source_comment_id=str(comment['commentID']),
														 article_url=fb_post.article_link,
														 comment_message=comment['commentBody'],
														 created_timestamp=datetime.utcfromtimestamp(
															 float(comment['createDate'])),
														 trusted_Count=comment['trusted'], user_id=comment['userID'],
														 reply_Count=comment['replyCount'],
														 sharing_Count=comment['sharing'],
														 recommendation_Count=comment['recommendations'],
														 editors_Selection=comment['editorsSelection'],
														 times_People_Count=comment['timespeople'],
														 user_location=str(comment['userLocation']), logical_parent=key
														 )
						reply_comment.put()
					# except db.BadValueError:
					# logging.info ('error found with comment: '+str(comment['userID']))
					# pass
			logging.info('finished processing page: ' + str(params['offset']))
			params['offset'] = params['offset'] + 25
			url_params = urllib.urlencode(params)
			full_url = url_base + '?' + url_params
			response = json.loads(request_until_succeed(full_url, 3))
			time.sleep(5)