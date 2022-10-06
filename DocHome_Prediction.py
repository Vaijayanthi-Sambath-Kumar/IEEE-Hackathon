
def pred_disease(string):
    user_symptoms=str(string).lower().split(',')

    # importing all necessary libraries
    import pickle
    import numpy as np
    import pandas as pd
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    from nltk.corpus import wordnet 
    import requests
    import re
    from bs4 import BeautifulSoup
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    from nltk.tokenize import RegexpTokenizer
    from itertools import combinations
    import nltk
    import joblib
    
    
    # returns the list of synonyms of the input word 
    def synonyms(term):
        synonyms = []
        response = requests.get('https://www.thesaurus.com/browse/{}'.format(term))
        soup = BeautifulSoup(response.content,  "html.parser")
        try:
            container=soup.find('section', {'class': 'MainContentContainer'}) 
            row=container.find('div',{'class':'css-191l5o0-ClassicContentCard'})
            row = row.find_all('li')
            for x in row:
                synonyms.append(x.get_text())
        except:
            None
        for syn in wordnet.synsets(term):
            synonyms+=syn.lemma_names()
        return set(synonyms)

    # utlities for pre-processing
    stop_words = stopwords.words('english')
    lemmatizer = WordNetLemmatizer()
    splitter = RegexpTokenizer(r'\w+')
    
    #df_comb -> Dataframe consisting of dataset generated by combining symptoms for each disease.*
    #df_norm -> Dataframe consisting of dataset which contains a single row for each diseases with all the symptoms for that corresponding disease.*
    #Dataset contains 261 diseases and their symptoms**

    df_comb = pd.read_csv('dis_sym_dataset_comb.csv') # Disease combination
    df_norm = pd.read_csv('dis_sym_dataset_norm.csv') # Individual Disease

    X = df_comb.iloc[:, 1:]
    Y = df_comb.iloc[:, 0:1]

    # List of symptoms
    dataset_symptoms = list(X.columns)
    
    # Preprocessing the input symptoms
    processed_user_symptoms=[]
    for sym in user_symptoms:
        sym=sym.strip()
        sym=sym.replace('-',' ')
        sym=sym.replace("'",'')
        sym = ' '.join([lemmatizer.lemmatize(word) for word in splitter.tokenize(sym)])
        processed_user_symptoms.append(sym)
        
    # Taking each user symptom and finding all its synonyms and appending it to the pre-processed symptom string
    user_symptoms = []
    for user_sym in processed_user_symptoms:
        user_sym = user_sym.split()
        str_sym = set()
        for comb in range(1, len(user_sym)+1):
            for subset in combinations(user_sym, comb):
                subset=' '.join(subset)
                subset = synonyms(subset) 
                str_sym.update(subset)
        str_sym.add(' '.join(user_sym))
        user_symptoms.append(' '.join(str_sym).replace('_',' '))
    
    # Loop over all the symptoms in dataset and check its similarity score to the synonym string of the user-input 
    # symptoms. If similarity>0.5, add the symptom to the final list
    found_symptoms = set()
    for idx, data_sym in enumerate(dataset_symptoms):
        data_sym_split=data_sym.split()
        for user_sym in user_symptoms:
            count=0
            for symp in data_sym_split:
                if symp in user_sym.split():
                    count+=1
            if count/len(data_sym_split)>0.5:
                found_symptoms.add(data_sym)
    found_symptoms = list(found_symptoms)
    
    sample_x = [0 for x in range(0,len(dataset_symptoms))]
    for val in found_symptoms:
        sample_x[dataset_symptoms.index(val)]=1
        
    #Loading the model
    with open('model_pkl', 'rb') as file:
        mlp = pickle.load(file)
    # Predict disease
    prediction = mlp.predict_proba([sample_x])
    
    k = 10
    diseases = list(set(Y['label_dis']))
    diseases.sort()
    topk = prediction[0].argsort()[-k:][::-1]
    
    topk_dict = {}
    # Show top 10 highly probable disease to the user.
    for idx,t in  enumerate(topk):
        match_sym=set()
        row = df_norm.loc[df_norm['label_dis'] == diseases[t]].values.tolist()
        row[0].pop(0)

        for idx,val in enumerate(row[0]):
            if val!=0:
                match_sym.add(dataset_symptoms[idx])
        prob = (len(match_sym.intersection(set(found_symptoms)))+1)/(len(set(found_symptoms))+1)
        prob *= 0.9026598754951896
        topk_dict[t] = prob
        
    diseases_final=[]
    probs=[]
    topk_sorted = dict(sorted(topk_dict.items(), key=lambda kv: kv[1], reverse=True))
    for key in topk_sorted:
        prob = topk_sorted[key]*100
        diseases_final.append(diseases[key])
        probs.append(str(round(prob, 2))+"%")
    
    wiki_dis=[]
    for i in diseases_final:
        temp = i.split('(')[0].capitalize()
        temp=temp.replace(" ","_")
        wiki_dis.append(temp)
        
    def clean_wikitext(text):
        text=re.sub(r'\[.*\]','',text) # Remove citation text  
        text = text[:-2:]
        return text
    
    #Extracting information regarding treatment of predicted diseases from wikipedia
    base_url='https://en.wikipedia.org/wiki/'
    texts=[]
    for dis in wiki_dis:
        response = requests.get(base_url+dis)
        soup = BeautifulSoup(response.content,  "html.parser")
        container = soup.find('span',{'id':'Management'})
        if container is None:
            container = soup.find('span',{'id':'Treatment'})
        if container is not None:
            temp = container.parent.find_next_sibling('p')
            text=(clean_wikitext(temp.text))+'. '
            if temp is not None:
                temp1 = temp.find_next_sibling('p')
                if temp1 is not None:
                        text+=' '+(clean_wikitext(temp1.text))+'. '
                        temp2 = temp1.find_next_sibling('p')
                        if temp2 is not None:
                            text+=(clean_wikitext(temp2.text))+'. '
            texts.append(text)
        else:
            texts.append('Sorry! We currently do not have a treatment available for this disease')
            
    final=[]
    for i in range(10):
        final.append([diseases_final[i], probs[i], texts[i]])
    
    return final