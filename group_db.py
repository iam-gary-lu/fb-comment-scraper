from google.appengine.ext import ndb
from datetime import datetime, date

class error(ndb.Model):
    timestamp = ndb.DateTimeProperty( repeated=True)
    fb_entity = ndb.StringProperty()
    entity = ndb.StringProperty()
    type = ndb.StringProperty(choices=['COMMENT','FB_POST', 'MULTI_FB_POST'])
    url = ndb.StringProperty()
    count = ndb.IntegerProperty()

class duplicate(ndb.Model):
    duplicates = ndb.JsonProperty()
    num_duplicates = ndb.IntegerProperty()
    total_duplicates = ndb.IntegerProperty()
    addressed = ndb.BooleanProperty(default=False)
    timestamp = ndb.DateTimeProperty(auto_now_add=True)

class fb_post(ndb.Model):
    nxt_comment_scrape_date = ndb.DateTimeProperty(auto_now_add=True)
    last_comment_scrape_date = ndb.DateTimeProperty()
    ignore_count = ndb.IntegerProperty(default=0) #when ignore_count =3, nxt_comment_scrape_date will not be updated
    group_name = ndb.StringProperty()
    fb_page_id = ndb.StringProperty()
    snippet = ndb.TextProperty() #fb's 'message' parameter
    post_name = ndb.StringProperty() #fb's 'name' parameter
    fb_post_id = ndb.StringProperty()
    link_type = ndb.StringProperty()
    article_link = ndb.StringProperty()
    fb_post_timestamp = ndb.DateTimeProperty()
    num_comments = ndb.IntegerProperty()
    num_comments_ds = ndb.IntegerProperty(default=0)
    comment_diff = ndb.ComputedProperty(lambda self: self.num_comments - self.num_comments_ds)
    num_shares = ndb.IntegerProperty()
    num_likes = ndb.IntegerProperty()
    num_loves = ndb.IntegerProperty()
    num_wows = ndb.IntegerProperty()
    num_hahas = ndb.IntegerProperty()
    num_sads = ndb.IntegerProperty()
    num_angrys = ndb.IntegerProperty()
    num_thankfuls = ndb.IntegerProperty()
    total_reaction = ndb.IntegerProperty()

class reddit_post(ndb.Model):
    reddit_post_id = ndb.StringProperty()
    url = ndb.StringProperty()
    score = ndb.IntegerProperty()
    timestamp = ndb.DateTimeProperty()
    comments_num = ndb.IntegerProperty()

class setting(ndb.Model):
    name = ndb.StringProperty()
    value = ndb.KeyProperty(kind=classification_scheme.kind())

class classification_scheme(ndb.Model):
    classification_choices = ndb.StringProperty(repeated=True)
    question = ndb.StringProperty()
    scheme_id = ndb.StringProperty()
    human_classification = ndb.BooleanProperty()

class classification(ndb.Model):
    classification = ndb.StringProperty()
    timestamp = ndb.DateTimeProperty(auto_now_add=True)
    scheme_id = ndb.StringProperty()
    signin_id = ndb.StringProperty()


class comment(ndb.Model):
    source = ndb.StringProperty()
    source_comment_id = ndb.StringProperty()
    source_parent_post_id = ndb.StringProperty()
    source_parent_comment_id = ndb.StringProperty()
    user_id = ndb.StringProperty()
    logical_parent = ndb.KeyProperty()
    comment_message = ndb.TextProperty()
    created_timestamp = ndb.DateTimeProperty()
    classifications = ndb.StructuredProperty(classification, repeated=True)
    #below are fb specific fields
    num_shares = ndb.IntegerProperty()
    num_likes = ndb.IntegerProperty()
    num_loves = ndb.IntegerProperty()
    num_wows = ndb.IntegerProperty()
    num_hahas = ndb.IntegerProperty()
    num_sads = ndb.IntegerProperty()
    num_angrys = ndb.IntegerProperty()
    num_thankfuls = ndb.IntegerProperty()
    total_reaction = ndb.IntegerProperty()
    #below are nytimes specific fields
    #trusted_Count = ndb.IntegerProperty()
    #user_id= ndb.IntegerProperty()
    #reply_Count = ndb.IntegerProperty()
    #sharing_Count = ndb.IntegerProperty()
    #recommendation_Count = ndb.IntegerProperty()
    #editors_Selection = ndb.BooleanProperty()
    #times_People_Count = ndb.IntegerProperty()
    #user_location = ndb.StringProperty()

    #below are reddit specific fields
    permalink_reddit = ndb.StringProperty()
    score_reddit = ndb.IntegerProperty()
    upvotes_reddit = ndb.IntegerProperty()
    downvotes_reddit = ndb.IntegerProperty()
    likes_reddit = ndb.IntegerProperty()
    reports_num_reddit = ndb.IntegerProperty()