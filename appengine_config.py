from google.appengine.ext import vendor

vendor.add('certifi')
vendor.add('chardet')
vendor.add('urllib3')
vendor.add('requests')
vendor.add('requests-toolbelt')
vendor.add('prawcore')
vendor.add('praw')
vendor.add('dateutil')

def webapp_add_wsgi_middleware(app):
	from google.appengine.ext.appstats import recording
	app = recording.appstats_wsgi_middleware(app)
	appstats_CALC_RPC_COSTS = True
	return app