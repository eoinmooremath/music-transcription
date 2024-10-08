import streamlit as st
import sounddevice as sd
import wave
import tempfile
import os
import assemblyai as aai
import requests
import re
import statistics
from collections import Counter
import json



st.set_page_config(layout="wide")




musixmatch_keys = ['6a00460767076f95b798c29886615dd0','592762b80ff8a28a4cf00cec347c72ad', '882fc7ce4a1040f771b9ee4ca1c02db1','1f9a5ec283e7e2c347b884aba10a0457']
# '6a00460767076f95b798c29886615dd0' eoin.moore32
# '592762b80ff8a28a4cf00cec347c72ad'	 eoin12345abc
# '882fc7ce4a1040f771b9ee4ca1c02db1'  eoinmooremath
# '1f9a5ec283e7e2c347b884aba10a0457' emoore
aai.settings.api_key = "89b9e6a5fd794944a6ec9875a7d90a72"


#############################################################
################## Musixmatch API code ######################
def request_musixmatch(input,flag,keys):
    success=False

    for api_key in keys:   #we will try out multiple keys, because sometimes musixmatch sudenly stops accepting my api_key temporarily     
        if flag == 'track':
            url = 'https://api.musixmatch.com/ws/1.1/track.get'
            params = {
                'track_id': input,
                'apikey': api_key
            }
        elif flag == 'album':
            url = 'https://api.musixmatch.com/ws/1.1/album.get'
            params = {
                'album_id': input,
                'apikey': api_key
            }
        elif flag == 'put_lyrics':
            url = 'https://api.musixmatch.com/ws/1.1/track.search'
            params = {
                'q_lyrics': input,
                'apikey': api_key,
                'page_size': 100
            }    
        elif flag == 'get_lyrics':
            url = 'https://api.musixmatch.com/ws/1.1/track.lyrics.get'
            params = {
                'track_id': input,
                'apikey': api_key
            }
        response = requests.get(url, params=params)
        data = response.json()
        if data['message']['header']['status_code']==200:
            success=True #if ever we have a success, this is the key we will work with.
            break

    if success == False:
        return data['message']['header']['status_code'] # if have never have success, return the error status code
    else:
        if flag == 'get_lyrics':        
            return data['message']['body']['lyrics']['lyrics_body'] #only in the special case of getting lyrics, do we want returned text, which is simply the lyrics.
        else:    
            return data

def split_text(text):
    split_pattern = r'[ \?.,!]+'
    tokens = re.split(split_pattern, text)
    tokens = [token for token in tokens if token]    
    return tokens

def group_text(tokens,L):
    results=[]
    word_groups = []
    for k in range(0, len(tokens)-L+1):
        words = tokens[k:k+L]
        word_groups = ' '.join(w for w in words)
        results.append(word_groups)
    return results
    
def get_track_ids_from_lyrics(lyric, keys):   
    # suppose the lyric as L words. Search for the entire lyric (after a little bit of cleaning.) If there are no results, search
    # for the first L-1 words, and the last L-1 words. If no results, search in chunks of L-2 words, etc. After you find one result, search again
    # a number of times equal to the iterations parameter for good measure. 
    # each search request returns up to 100 possible songs and which we track via their track id.  For all the successful hits, add those track ids to a list.
    # the idea is the better the result, the more hits it will generate.  At the end, give the top 5 results of maximum frequency in decreasing order of track_rating. 
    
    if len(lyric)==0: #if the length of lyric is zero, then the computer didnt hear anything. Pass that along as a special code 0
        return 0 
    else:
        search_complete = False
        lyric = split_text(lyric)
        length = len(lyric) 
        track_ids = []
        total_song_list = []
        while search_complete == False:
            lyric_attempts = group_text(lyric,length) # get the various strings we will search for
            for k in range(len(lyric_attempts)): #we have broken up our string into k chunks to search each for matching lyrics
                results = request_musixmatch(lyric_attempts[k], 'put_lyrics',keys) 
                if isinstance(results,(int,float)): #if ever the musixmatch API fails, then end the process and  output the status code of the failed request, which is a number.  
                    return results
                elif len(results['message']['body']['track_list'])!=0:
                    # if we have at least one result, our search is complete after the for loop finished
                    search_complete = True
                    local_song_list = results['message']['body']['track_list']
                    # total_song_list = total_song_list + local_song_list 
                    for j in range(len(local_song_list)):
                        total_song_list.append(local_song_list[j]['track'])
                        track_ids.append(local_song_list[j]['track']['track_id'])
                    
            # after we finish the for loop, if we got matches, exit the while-loop. Otherwise, check to see if we are searching single words now. If so, we are done.
            # if not, decrease the length of our grouping, and try searching again.

            if length ==1:
                search_complete = True
            
            length = length-1

        # for good measure, we will search again, assuming our length > 1. This is to improve the search results, now that we have at least one.     

        if length>1:
            length=length-1
            lyric_attempts = group_text(lyric,length)
            for k in range(len(lyric_attempts)):
                results = request_musixmatch(lyric_attempts[k],'put_lyrics',keys)
                if isinstance(results,(int,float)):
                    break  
                elif len(results['message']['body']['track_list'])!=0:
                    local_song_list = results['message']['body']['track_list']
                    for j in range(len(local_song_list)):
                        total_song_list.append(local_song_list[j]['track'])
                        track_ids.append(local_song_list[j]['track']['track_id'])
        
        # it is possible we had successful searches but empty search results. This will result in track_ids == [].
        if len(track_ids)==0:
            return 0  # 0 will be our code for no search results
        else: 
            # Below we are going to select songs based on how frequently they arise and their popularity.  This requires some experimentation.
            # I find that simply requiring count >= top_frequency is too strong, and gives strange songs noone heard of. 
            # There are six possibilities I will choose from:            
            #1st, 2nd most popular of the all songs.  1st, 2nd most popular of all >=middle songs.  #1st or 2nd most popular of all songs as long as they are at least average songs
            
            #      the conditions would be:
            #1st, 2nd most popular of all songs:  
            #(a)   song for song in total_song_list if song['track_id'] in top_one_ids_all
            #(b)   song for song in total_song_list if song['track_id'] in top_two_ids_all

            #1st, 2nd most popular of all mid songs:
            #(c)   song for song in total_song_list if song['track_id'] in top_one_ids_mid
            #(d)   song for song in total_song_list if song['track_id'] in top_two_ids_mid

            #1st, 2nd most popular of all songs, as long as they are at least mid 
            #(e)   song for song in total_song_list if song['track_id'] in top_one_ids_all and song['track_rating']>= mid_popular
            #(f)   song for song in total_song_list if song['track_id'] in top_two_ids_all and song['track_rating']>= mid_popular

            #experiments show a,c,e are bad results.  Note that f is a subset of d .  
            # The logic we will choose is:  try f. If empty, try d.


            # songs_list is a list of dictionaries with duplicates. We want the list of unique song dictionaries.
            total_song_list_unique = [json.loads(item) for item in {json.dumps(d, sort_keys=True) for d in total_song_list}]


            # get the rating for each unique song
            ratings = [x['track_rating'] for x in total_song_list_unique]
            
            # this rating lets us get the median rating
            mid_popular = statistics.median((ratings))

            # these are the ids of tracks which have at least median rating
            mid_song_ids = [x['track_id'] for x in total_song_list if x['track_rating'] >= mid_popular]            
        
            # we want to find out how many times a track pops up in our total_song_list.  The more times the more likely that's our match.
            frequency_all = Counter(track_ids)

            # the below code is to get the second highest frequency, i.e. the songs with the second-most results.
            frequencies_all_unique = sorted(set(frequency_all.values()), reverse=True)
            top_frequency_all = frequencies_all_unique[0]
            if len(frequencies_all_unique) >1:
                second_frequency_all = frequencies_all_unique[1]
            else: 
                second_frequency_all = top_frequency_all  

            # get the second highest frequency of the songs which are at least mid-popular
            frequency_mid = Counter(mid_song_ids)
            frequencies_mid_unique = sorted(set(frequency_mid.values()), reverse=True)
            top_frequency_mid = frequencies_mid_unique[0]
            if len(frequencies_mid_unique) >1:
                second_frequency_mid = frequencies_mid_unique[1]
            else: 
                second_frequency_mid = top_frequency_mid
            
            # get the ids of those songs which were at least the second-most results, among all songs and among mid-popular songs
            top_two_ids_all = [item for item, count in frequency_all.items() if count >= second_frequency_all]
            top_two_ids_mid = [item for item, count in frequency_mid.items() if count >= second_frequency_mid]    
           
            ## top_one_ids_all = [item for item, count in frequency_all.items() if count >= top_frequency_all] 
            ## top_one_ids_mid = [item for item, count in frequency_mid.items() if count >= top_frequency_mid]
            

            # get the song dictionaries of those unique songs if their track is in among the top-two selected of all songs and are at least 
            # mid-popular; sort my reverse popularity (track rating).
            sorted_songs = sorted(
                ( song for song in total_song_list_unique if song['track_id'] in top_two_ids_all and song['track_rating']>= mid_popular), 
                key = lambda x: x['track_rating'], reverse=True )
            #if the above yields no results, loosen the criteria
            if len(sorted_songs)==0:
                sorted_songs= sorted(
                    ( song for song in total_song_list_unique if song['track_id'] in top_two_ids_mid), 
                    key = lambda x: x['track_rating'], reverse=True )
    
            sorted_song_list = [song['track_id'] for song in sorted_songs][0:10]
            return sorted_song_list


def get_song_info_from_track_ids(track_ids, keys):
    # Input is a list of track ids.  Output should be a list of dictionaries.  
    # Each dictionary contains information like artist, album, song title, lyrics, etc. corresponding to that track id.
    results =[]
    if isinstance(track_ids, (int,float)): #if track_ids is just a number, than it is an error status code
        track_info=''
        artist_name=''
        song_title=''
        album_name=''
        album_id=''
        album_data=''
        release_date = ''
        lyrics=''
        found = False
        status_code = track_ids
        info ={'artist_name':artist_name,'song_title':song_title, 'album_name':album_name, 'album_id':album_id, 'release_date':release_date, 'lyrics':lyrics, 'found':found, 'status_code':status_code}
        results.append(info)
    else:
        for k in range(len(track_ids)):
            data = request_musixmatch(track_ids[k],'track',keys)
            if not isinstance(data,(int,float)): #if we didn't get an error code from request_musixmatch
                if 'message' in data and 'body' in data['message'] and 'track' in data['message']['body']:
                    track_info = data['message']['body']['track']
                    artist_name = track_info['artist_name']
                    song_title = track_info['track_name']
                    album_name = track_info['album_name']
                    album_id = track_info['album_id']
                    album_data = request_musixmatch(album_id,'album',keys)
                    release_date = album_data['message']['body']['album']['album_release_date']
                    lyrics = request_musixmatch(track_ids[k],'get_lyrics',keys)
                    status_code = data['message']['header']['status_code']
                    found = True
                else:
                    track_info=''
                    artist_name=''
                    song_title=''
                    album_name=''
                    album_id=''
                    album_data=''
                    release_date = ''
                    lyrics=''
                    found = False   
                    status_code = data['message']['header']['status_code'] 
            else:
                track_info=''
                artist_name=''
                song_title=''
                album_name=''
                album_id=''
                album_data=''
                release_date = ''
                lyrics=''
                found = False
                status_code = data['message']['header']['status_code']
            info ={'artist_name':artist_name,'song_title':song_title, 'album_name':album_name, 'album_id':album_id, 'release_date':release_date, 'lyrics':lyrics, 'found':found, 'status_code':status_code}
            results.append(info)
    return results

def get_songs_from_lyrics(lyrics,keys):
    track_ids = get_track_ids_from_lyrics(lyrics, keys)
    songs = get_song_info_from_track_ids(track_ids, keys)
    return songs
    
            





            


##############################################################
################ Assembly AI Transcriber #####################


# Initialize AssemblyAI Transcriber
transcriber = aai.Transcriber()

def record_audio(duration):
    """Record audio for a given duration."""
    fs = 44100  # Sample rate
    audio_data = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype='int16')
    sd.wait()  # Wait until recording is finished
    return audio_data

def save_audio_to_wav(audio_data, filename):
    """Save audio data to a WAV file."""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit audio
        wf.setframerate(44100)
        wf.writeframes(audio_data.tobytes())

def delete_old_file():
    """Delete the old temporary file if it exists."""
    if 'audio_file' in st.session_state and st.session_state.audio_file:
        try:
            os.remove(st.session_state.audio_file)  # Delete the old audio file
            st.session_state.audio_file = None  # Clear the old file path
        except OSError as e:
            st.warning(f"Error deleting old file: {e}")


##############################################################
######################### Streamlit ##########################
padding_top = 0


def main():
    
    col1, col2, col3, col4 = st.columns([1.5, 1, 4.5,1.5])  



    # Column 1: Explanation text
    with col1:
        st.markdown(
            """
            ### Project Explanation
            This project allows users to record audio, transcribe lyrics, and search for song information 
            based on the transcription. You can record up to 10 seconds of audio, and the app will 
            attempt to match the lyrics to popular songs. 
            
            The lyrics are transcribed by Assembly AI, 
            the words are matched to songs using the Musix Match database, and the user interface is done with Streamlit.
           """
        )
    
    #Column 2: The main co
    with col3:  
        st.title("Lyric Search")

        # Use session_state to store data across reruns
        if 'transcription' not in st.session_state:
            st.session_state.transcription = None
        if 'audio_file' not in st.session_state:
            st.session_state.audio_file = None
        if 'selected_song' not in st.session_state:
            st.session_state.selected_song = None
        if 'recording' not in st.session_state:
            st.session_state.recording = False  # Flag to track if recording is happening
        if 'audio_data' not in st.session_state:
            st.session_state.audio_data = None  # Store recorded audio data
        if 'song_info' not in st.session_state:
            st.session_state.song_info = None
        if 'selected_index' not in st.session_state:
            st.session_state.selected_index=None
        if 'song_options' not in st.session_state:
            st.session_state.song_options = []  # Initialize song options

        # Step 1: Record new audio and delete old file if the button is pressed
        if st.button("Record Audio for 10 seconds"):
            # Delete old temporary audio file if it exists
            delete_old_file()

            st.session_state.song_options = []  # Clear old song options
            st.session_state.selected_index = None  # Clear selected index

            # Start recording and set the flag
            st.session_state.recording = True
            st.rerun()

        # Step 2: Show recording message only while recording
        if st.session_state.recording:
            st.write("Recording... Please speak now.")
            st.session_state.audio_data = record_audio(10)  # Store the recorded audio data
            st.session_state.recording = False  # Clear recording flag after done
            st.rerun()

        # Step 3: Save and display new audio
        if st.session_state.audio_data is not None and st.session_state.audio_file is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                save_audio_to_wav(st.session_state.audio_data, tmp_file.name)
                st.session_state.audio_file = tmp_file.name  # Store the new file path in session_state
                st.success("New audio recorded successfully!")
            
            # Transcribe the new audio file
            with st.spinner("Transcribing..."):
                transcript = transcriber.transcribe(st.session_state.audio_file)
                st.session_state.transcription = transcript.text  # Store the transcription result

            st.rerun()

        # Step 4: Display the audio player if an audio file exists
        if st.session_state.audio_file:
            st.audio(st.session_state.audio_file)

        # Step 5: Display transcription if it exists
        if st.session_state.transcription:
            st.subheader("Transcription Result:")
            st.write(st.session_state.transcription)
            # Get possible song titles based on the transcription
            #if 'song_options' not in st.session_state:
            if not st.session_state.song_options:
                with st.spinner("Getting song results..."):
                    song_options = get_songs_from_lyrics(st.session_state.transcription, musixmatch_keys)
                    st.session_state.song_options = song_options 
            else:
                song_options = st.session_state.song_options

            # First we error handle the transcription based on the status codes we read. If all is well, then display the results.
            if song_options[0]['status_code']==0:
                st.write("Sorry! Musixmatch couldn\'t find any lyrics matching your transcript. Want to try again?")
            elif not (song_options[0]['status_code']==200):
                st.write("Sorry, something went wrong. We were unable to retrieve results from the Musixmatch service.")
            else:   
                # Divide the layout into two columns
                cola, colb = st.columns(2)

                with cola:
                    st.subheader("Possible Songs:")
                    if 'selected_index' not in st.session_state:
                        st.session_state.selected_index = 0  # Set default to first song index
                    else:
                        st.session_state.selected_index = st.radio("Select a song title:", range(len(song_options)), format_func=lambda idx: song_options[idx]['song_title']+ ' by '+st.session_state.song_options[idx]['artist_name'])

                # Step 6: Display album info based on selected song
                with colb:
                    if st.session_state.selected_index is not None:
                        idx = st.session_state.selected_index
                        st.subheader("Song Info:")
                        st.write(f"**Artist:** {song_options[idx]['artist_name']}")
                        st.write(f"**Album:** {song_options[idx]['album_name']}  **Release Date:** {song_options[idx]['release_date']}")
                        st.write(song_options[idx]['lyrics'])
        else: 
            if st.session_state.audio_data is not None:
                st.write("Sorry, we couldn't successfully transcribe any text. Please try again with a clearer audio signal.")

if __name__ == "__main__":
    main()

    

