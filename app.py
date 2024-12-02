import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
import openai
import os
import re
import ast
import csv

app = Flask(__name__)

os.environ["OPENAI_API_KEY"] = "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"

excel_file = 'updated_data.xlsx'
df = pd.read_excel(excel_file)

def generate_txt(decision_text, output_txt='decision.txt'):
    with open(output_txt, 'w', encoding='utf-8') as f:
        f.write(decision_text)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["POST"])
def search():
    query = request.json.get("query")
    search_by = request.json.get("search_by")

    result = pd.DataFrame()

    if query:
        if search_by == "id":
            try:
                query_int = int(query)
                result = df[df['id'] == query_int]
            except ValueError:
                pass
        elif search_by == "relator":
            result = df[df['Relator'].str.contains(query, case=False, na=False)]
        elif search_by == "process_number":
            result = df[df['Process_Number'] == query]

        if not result.empty:
            decisions = result.to_dict(orient='records') 
            return jsonify({"decisions": decisions})

    return jsonify({"error": "No decision found."})




@app.route("/get_txt")
def get_txt():
    return send_file("decision.txt", as_attachment=False)

def map_laws(decision_text):
    prompt = f"""
    Leia o seguinte texto de uma decisão judicial e extraia as leis mencionadas e os artigos dessas respectivas leis.
    Retorne o resultado exclusivamente no formato de lista de tuplas, onde cada tupla tem as chaves 'artigo', 'lei' e 'ano'.
    Certifique-se de remover os pontos das leis (ex: Lei 8.666 deve ser '8666') e retorne apenas números válidos.

    Exemplo de resposta:
    [("33", "8666", "2022"), ("44", "10406", "2002")]

    Responda estritamente no formato de lista de tuplas, sem qualquer explicação adicional.

    Texto da decisão:
    {decision_text}
    """
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": """
            Você é um assistente jurídico que extrai leis mencionadas em decisões judiciais.
            Atente-se para que as leis vêm geralmente com um ponto no meio (por exemplo, Lei 8.666),
            mas preciso que a resposta exclua esse ponto (ou seja, a resposta deve ser apenas 8666).
            Responda apenas no formato estrito especificado (lista de tuplas) sem explicações.
            """},
            {"role": "user", "content": prompt}
        ],
    )

    extracted_laws = response.choices[0].message.content.strip()
    extracted_laws = re.sub(r"[^\[\]\(\)\d,'\"]", "", extracted_laws).strip()
    try:
        extracted_laws = ast.literal_eval(extracted_laws)
    except (ValueError, SyntaxError) as e:
        raise ValueError(f"Erro ao interpretar a resposta: {e}")

    unique_laws = list(dict.fromkeys(extracted_laws))

    return unique_laws

def buscar_artigo_no_csv(numero_lei, numero_artigo, caminho_arquivo):

    with open(caminho_arquivo, mode='r', encoding='utf-8', errors='replace') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            if row['Lei'].strip() == numero_lei:
                if row['Artigo'].strip() == numero_artigo:
                    return (row['Lei'], row['Artigo'], row['Texto'])
    return None

def generate_response(query, document_text, contexto):
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": f"Você é um assistente jurídico que responde perguntas sobre decisões. Pergunta: {query}. Decisão: {document_text}. Utilize o texto na íntegra das seguintes leis para ajudar na sua resposta: {contexto}"},
        ]
    )
    answer = response.choices[0].message.content
    return answer

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    document_text = request.json.get("decision_text")  
    laws = map_laws(document_text)
    context = []
    for i in laws:
        law = buscar_artigo_no_csv(i[1], i[0], 'articles.csv')
        if law:
            context.append(law)
        else:
            None

    if user_message and document_text:

        response = generate_response(user_message, document_text, context)
        return jsonify({"response": response, "context": laws})
    
    return jsonify({"response": "Please provide a message and decision text."})

if __name__ == "__main__":
    app.run(debug=True)
