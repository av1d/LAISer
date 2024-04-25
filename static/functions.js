/*
    MIT License

    Copyright (c) 2024 av1d

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
*/


/*
   place cursor in the input_text area on page load
*/
document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('input_text').focus();
});

/*
   auto-expand the text input area
*/
function autoExpand(textarea) {
    // Reset textarea height to default in case it shrinks
    textarea.style.height = 'auto';
    // Calculate the height of the content and limit it to 20vw
    const maxHeight = 15 * (window.innerWidth / 100); // Convert 15vw to pixels
    const newHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = newHeight + 'px';
}

/*
   listen for a response from ollam or llama.cpp then append the messages
   to the chat dialog and hide the animation once a message is
   received
*/
const chatMessages = document.getElementById('chat-messages');
const form = document.getElementById('user-input');
const loader = document.querySelector('.loader');
const loaderBefore = document.querySelector('.loader:before');
const pupil = document.querySelector('.pupil');
const sendIcon = document.querySelector('.send-icon');

form.addEventListener('submit', function(event) {
    event.preventDefault();

      // Generate a random hash
    const randomHash = Math.random().toString(36).substring(2, 34);

    fetch('/search', {
        method: 'POST',
        body: new FormData(form)
    })
    .then(response => response.json())
    .then(data => {
        const newResponse = document.createElement('div');
        newResponse.classList.add('message', 'received');
        newResponse.setAttribute('id', randomHash);
        newResponse.innerHTML = `<p>${data.result}</p>`;
        chatMessages.appendChild(newResponse);

        // Create and insert buttons
        const expandBtn = document.createElement('button');
        expandBtn.setAttribute('id', randomHash);
        expandBtn.setAttribute('class', 'sources-button');
        expandBtn.innerHTML = '<small>cited sources</small>';
        expandBtn.addEventListener('click', function() {
            toggleSources(this);
        });
        newResponse.appendChild(expandBtn);

        const copyAllBtn = document.createElement('button');
        copyAllBtn.setAttribute('id', 'copyAllBtn');
        copyAllBtn.setAttribute('class', 'copy-all-button');
        copyAllBtn.innerHTML = '<small>copy with sources</small>';
        copyAllBtn.addEventListener('click', function() {
            copyContents(this);
        });
        newResponse.appendChild(copyAllBtn);

        const copyBtn = document.createElement('button');
        copyBtn.setAttribute('id', 'copyBtn');
        copyBtn.setAttribute('class', 'copy-button');
        copyBtn.innerHTML = '<small>copy</small>';
        copyBtn.addEventListener('click', function() {
            copyAnswerResponseContent(this);
        });
        newResponse.appendChild(copyBtn);

        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Hide loader and loader:before and unhide send-icon
        loader.style.display = 'none';
        pupil.style.display = 'none';
        if (loaderBefore) {
            loaderBefore.style.display = 'none';
        }
        sendIcon.style.display = 'block';
    })
    .catch(error => {
        console.error('Error:', error);
    });

    document.getElementById('input_text').value = '';
});

/* 
   behavior for text entry (enter to send, allow shift+enter for newline)
*/
const inputTextElement = document.getElementById('input_text');
const sendButton = document.querySelector('.send-button');

inputTextElement.addEventListener('keydown', function(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendButton.click();
  }
});


/*
   behaviors for sent message
*/
sendButton.addEventListener('click', function() {
    const inputText = inputTextElement.value.trim();

    if (inputText) {
        const newMessage = document.createElement('div');
        newMessage.textContent = inputText;
        newMessage.classList.add('message', 'sent');
        chatMessages.appendChild(newMessage);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        const sendIcon = document.querySelector('.send-icon');
        sendIcon.style.display = 'none';

        const loaderDivs = document.querySelectorAll('.loader, .loader:before, .pupil');
        loaderDivs.forEach(div => div.style.display = 'block');

        form.dispatchEvent(new Event('submit'));

        inputTextElement.style.height = 'auto';
        inputTextElement.value = ''; // Clear the textarea after sending
    }
});

/*
   buttons below answer (cited sources, copy buttons)
*/

// CITED SOURCES
function toggleSources(button) {
    // Find the parent element of the button
    const parentElement = button.parentElement;

    // Find the <ul> element with the "sources" class
    const sourcesList = parentElement.querySelector('.sources');

    sourcesList.style.display = (sourcesList.style.display === 'none' || sourcesList.style.display === '') ? 'block' : 'none';
}

// COPY WITH SOURCES
function copyContents(button) {
    var parentDiv = button.parentElement;
    var answerResponse = parentDiv.querySelector('#answer-response').textContent;
    var sources = parentDiv.querySelector('.sources').innerText;

    var combinedContent = answerResponse + '\n' + sources;

    // Copy the combined content to the clipboard
    var temp = document.createElement('textarea');
    temp.value = combinedContent;
    document.body.appendChild(temp);
    temp.select();
    document.execCommand('copy');
    document.body.removeChild(temp);
}

// COPY ONLY ANSWER
function copyAnswerResponseContent(button) {
    var answerDiv = button.parentElement.querySelector('#answer-response');
    var content = answerDiv.innerText;

    var textarea = document.createElement('textarea');
    textarea.value = content;

    document.body.appendChild(textarea);

    textarea.select();
    textarea.setSelectionRange(0, 99999);

    document.execCommand('copy');

    document.body.removeChild(textarea);
}
