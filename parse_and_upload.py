import json
import csv
import requests

csv_path = 'C:/Research/Insight_App/facebook_scraper/nytimes_facebook_comments_BASE_TEST.csv'
new_csv = 'huffpost_facebook_posts_BASE_TEST.csv'
local_host='http://localhost:8080'


	
def csv_upload():
	branch = '/upload'
	full_path = local_host+branch
	rows = []
	with open (new_csv, 'rb') as csvfile:
		reader = csv.DictReader(csvfile)
		for row in reader:
			
				rows.append(reader.next())
			#rows.append(row)
	#file = open(csv_path,'rb')
	#reader = csv.DictReader(file)
	
	#headers = {'status_id':'fb_post_id','status_type':'link_type','status_message':'snippet','status_published':'fb_post_timestamp'}
	
		
	print(rows)
	payload = json.dumps(rows)

	r = requests.post(full_path,data={'data':payload})
	print('request status code: '+str((r.status_code)))
	
def strip_empty():
	input = open(csv_path, 'rb')
	output = open (new_csv, 'wb')
	writer = csv.writer(output)
	for row in csv.reader(input):
		if any(row):
			writer.writerow(row)
	input.close()
	output.close()
	
	
	
	
	

if __name__ == '__main__':
    #strip_empty()
	csv_upload()

	