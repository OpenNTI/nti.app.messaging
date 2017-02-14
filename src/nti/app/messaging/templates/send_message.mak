${receiver['informal_name']},

% if plain_text_message:
	${plain_text_message}
% endif

% if not plain_text_message:
	You have a new message.
% endif

${sender['informal_name']}

To respond to this message please log back into (${request.application_url}) and click on the message icon in the top right corner. If you just hit reply, your email is stored in a file labeled “Didn’t Read Instructions” for the rest of your University career. Your permanent file. (Yes, it really exists.)
