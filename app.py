import openai
import streamlit as st
from bs4 import BeautifulSoup
import requests
import pdfkit
import time


assistant_id = 'asst_AVgXmpoOkMOUEdbFHWrS54zb'


client = openai

if "file_id_list" not in st.session_state:
    st.session_state.file_id_list = []

if "start_chat" not in st.session_state:
    st.session_state.start_chat = False

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

st.set_page_config(page_title="ChatGPT-like Chat App", page_icon=":speech_balloon:")


def scrape_website(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.get_text()

def text_to_pdf(text, filename):
    path_wkhtmltopdf = '/usr/local/bin/wkhtmltopdf'
    config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
    pdfkit.from_string(text, filename, configuration=config)
    return filename

def upload_to_openai(filepath):
    response = client.files.create(file=open(filepath, 'rb'), purpose='assistants')
    print(response)
    return response.id

st.sidebar.header("Configuration")

api_key = st.sidebar.text_input("Enter your OpenAI API Key", type="password")

if api_key:
    client.api_key = api_key
    st.sidebar.success("API Key Configured")

st.sidebar.header("Additional Features")

website_url = st.sidebar.text_input("Enter a website URL to scrape and organize into a PDF", key="website_url")

if st.sidebar.button("Scrape and Upload"):
    scraped_text = scrape_website(website_url)

    pdf_path = text_to_pdf(scraped_text, "scraped_text.pdf")

    file_id = upload_to_openai(pdf_path)

    st.session_state.file_id_list.append(file_id)


uploaded_file = st.sidebar.file_uploader("Upload a file to OpenAI embeddings", key="file_uploader")

if st.sidebar.button("Upload File"):
    if uploaded_file:
        with open(f"{uploaded_file.name}", "wb") as f:
            f.write(uploaded_file.getbuffer())
        additional_file_id = upload_to_openai(f"{uploaded_file.name}")
        print("additional_file_id:", additional_file_id)
        st.session_state.file_id_list.append(additional_file_id)
        st.sidebar.write(f"Additional File ID: {additional_file_id}")

# Display all file IDs
if st.session_state.file_id_list:
    st.sidebar.write("Uploaded File IDs:")
    for file_id in st.session_state.file_id_list:
        st.sidebar.write(file_id)
        # Associate files with the assistant
        assistant_file = client.beta.assistants.files.create(
            assistant_id=assistant_id, 
            file_id=file_id
        )

if st.sidebar.button("Start Chat"):
    if st.session_state.file_id_list:
        st.session_state.start_chat = True
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
        st.write("thread_id:", st.session_state.thread_id)
    else:
        st.sidebar.error("Please upload a file first")


def process_message_with_citations(message):
    message_content = message.content[0].text

    annotations = message_content.annotations if hasattr(message_content, 'annotations') else []
    citations = []

    for index, annotation in enumerate(annotations):
        # Replace the text with a footnote
        message_content.value = message_content.value.replace(annotation.text, f' [{index + 1}]')

        # Gather citations based on annotation attributes
        if (file_citation := getattr(annotation, 'file_citation', None)):
            # Retrieve the cited file details (dummy response here since we can't call OpenAI)
            cited_file = {'filename': 'cited_document.pdf'}  # This should be replaced with actual file retrieval
            citations.append(f'[{index + 1}] {file_citation.quote} from {cited_file["filename"]}')
        elif (file_path := getattr(annotation, 'file_path', None)):
            # Placeholder for file download citation
            cited_file = {'filename': 'downloaded_document.pdf'}  # This should be replaced with actual file retrieval
            citations.append(f'[{index + 1}] Click [here](#) to download {cited_file["filename"]}')  # The download link should be replaced with the actual download path

    # Add footnotes to the end of the message content
    full_response = message_content.value + '\n\n' + '\n'.join(citations)
    return full_response



st.title("ChatGPT-like Chat App")
st.write("This is a simple chat app that uses OpenAI's Chat API to generate responses to your messages. It is similar to the ChatGPT demo, but it uses the Chat API instead of the Completion API. This means that you can upload files to OpenAI and the AI will be able to use them to generate responses.")


if st.session_state.start_chat:
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-3.5-turbo-1106"
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
         with st.chat_message(message["role"]):
            st.markdown(message["content"])


    if prompt := st.chat_input("How may I help you?"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id, 
            role="user",
            content=prompt
        )

        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=assistant_id,
            instructions="Please answer the queries using the knowledge provided in the files.When adding other information mark it clearly as such.with a different color",
        )

        with st.spinner('Wait for it...'):
            while run.status != "completed":
                # add loading indicator
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(thread_id = st.session_state.thread_id, run_id = run.id)


        messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)

        assistant_messages_for_run = [
            message for message in messages 
            if message.run_id == run.id and message.role == "assistant"
        ]

        for message in assistant_messages_for_run:
            full_response = process_message_with_citations(message)

            st.session_state.messages.append({"role": "assistant", "content": full_response})

            with st.chat_message("assistant"):
                st.markdown(full_response)
else:
    st.write("Please upload files and click 'Start Chat' to begin the conversation.")
         
