import os
from datetime import datetime, date, timedelta
from shutil import disk_usage, move, copy2, rmtree
import smtplib
from email.message import EmailMessage
import logging
from dotenv import load_dotenv

logging.basicConfig(filename='teste_script_backup.log', level=logging.INFO)

load_dotenv()

def createTestDirectory():
  
  # Criar as pastas 'origem', 'destino' e 'buffer' se não existirem
  pastas = ['origem', 'destino', 'buffer']
  for pasta in pastas:
    if os.path.exists(pasta):
      rmtree(pasta)
    os.makedirs(pasta)
      

  # Define a data inicial e final
  data_inicio = datetime(2024, 2, 18)
  data_final = datetime(2024, 2, 26)

  # Loop sobre cada dia no período
  delta_dias = timedelta(days=1)
  data_atual = data_inicio

  while data_atual <= data_final:
    
    # Loop para gerar 5 arquivos para cada dia
    for i in range(1, 8):
      # Criar o nome do arquivo com o formato desejado
      nome_arquivo = f"arquivo_{data_atual.strftime('%Y%m%d')}_{i}.txt"
      caminho_arquivo = os.path.join('origem', nome_arquivo)
      
      # Criar o arquivo na pasta 'origem'
      with open(caminho_arquivo, 'w') as arquivo:
        arquivo.write(f"Este é o arquivo {nome_arquivo}")
      
      # Definir a data de modificação do arquivo
      data_modificacao = data_atual.timestamp()
      os.utime(caminho_arquivo, times=(data_modificacao, data_modificacao))
    
    # Avançar para o próximo dia
    data_atual += delta_dias
    
def convertBytesTo(bytes):

  kb = bytes / 1024
  mb = kb / 1024
  gb = mb / 1024

  if gb >= 1:
    return f"{gb:.2f} GB"
  
  elif mb >= 1:
    return f"{mb:.2f} MB"
  
  elif kb >= 1:
    return f"{kb:.2f} KB"
  
  else:
    return f"{bytes} bytes"

def getStorageInfo(directory):

  storage = disk_usage(directory)

  storageInfo = {
    'total': storage.total,
    'used': storage.used,
    'free': storage.free
  }

  return storageInfo

def getFilesToMove(directory):

  files = os.listdir(directory)
  totalSize = 0
  #currDate = datetime.today()
  currDate = datetime(2024, 2, 26) #Temporaria
  fileInfoList = []

  for file in files:

    if(file.endswith('txt')):

      filePath = os.path.join(directory, file)
      fileDate = datetime.fromtimestamp(os.stat(filePath).st_mtime)

      if(fileDate.date() != currDate.date()):

        fileSize = os.path.getsize(filePath)
        totalSize += fileSize

        fileInfo = {
          'name': file,
          'date': fileDate,
          'size': fileSize
        }

        fileInfoList.append(fileInfo)
      
  fileInfoList = sorted(fileInfoList, key=lambda x: x['date'])

  return {
    'files': fileInfoList,
    'totalSize': totalSize
  }

def transferFiles(files, fromPath, toPath, buffer):

  mouths = ['JANEIRO', 'FEVEREIRO', 'MARCO', 'ABRIL', 'MAIO', 'JUNHO', 'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO']

  response = {
    'moved_files': [],
    'status_type': 'success',
    'total_size': 0,
    'total_files': len(files)
  }

  #if files[0]['date'].year != currDate.year
  #TENHO QUE TRATAR O CASO DE TROCA DE ANO

  try:

    #currDate = datetime.now()
    currDate = datetime(2024, 2, 26) #simulando que hoje é segunda
    yearDirectoryPath = os.path.join(toPath, str(currDate.year))
    newMouthDirectoryPath = os.path.join(yearDirectoryPath, mouths[currDate.month - 1])
    oldMouthDirectoryPath = os.path.join(yearDirectoryPath, mouths[currDate.month - 2])

    # Verificando se a pasta do ano existe
    if not os.path.exists(yearDirectoryPath) or not os.path.isdir(yearDirectoryPath):
      os.makedirs(yearDirectoryPath)

    # Verificando se a pasta do mês existe
    if not os.path.exists(newMouthDirectoryPath) or not os.path.isdir(newMouthDirectoryPath):
      os.makedirs(newMouthDirectoryPath)

    for file in files:

      fromFilePath = os.path.join(fromPath, file["name"])
      bufferFilePath = os.path.join(buffer, file["name"])
      mouthFilePath = (newMouthDirectoryPath if file['date'].month == currDate.month else oldMouthDirectoryPath) + "\\" + file["name"]

      #COPIANDO PARA O BUFFER APENAS OS ARQUIVOS DOS DIAS UTEIS
      if file["date"].weekday() != 6 and file["date"].weekday() != 5:   
        copy2(fromFilePath, bufferFilePath)

      if(not move(fromFilePath, mouthFilePath)):
        response['error_message'] = f"Erro durante a transição do arquivo {file['name']}"
        response['status_type'] = 'error_file'
        break

      response['moved_files'].append(file) 
      response['total_size'] += file['size']

  except Exception as e:
    response['status_message'] = f'Ocorreu um problema durante a transição de arquivos:\n{e}'
    response['status_type'] = 'generic_error'
    logging.error(f"{e} ({currDate})")
  
  finally:
    response_log = ''
    
    logging.info(f"Informacoes sobre a transferencia\nArquivos Movidos: {len(response['moved_files'])}\nTotal de arquivos: {response['total_files']}\nCusto de armazenamento: {convertBytesTo(response['total_size'])}\n")
    
    for data in response['moved_files']:
      response_log += f"{data['name']} | {data['date']} | {convertBytesTo(data['size'])}\n"
      
    logging.info(f"\n{response_log}")
    
    rmtree("buffer")
    rmtree("destino")
    rmtree("origem")
    
def boot(fromPath, toPath, buffer):

  #EXECUTA O BACKUP APENAS NAS SEGUNDAS
  currDate = date.today()
  #if(currDate.weekday() != 0):
    #return

  try:
      
    #VERIFICANDO SE OS CAMINHOS EXISTEM E SÃO PASTAS
    for path in [fromPath, toPath, buffer]:
      if not os.path.exists(path):
        raise FileNotFoundError(f'O caminho ({path}) não existe!')
      if not os.path.isdir(path):
        raise NotADirectoryError(f'O caminho ({path}) não é um diretório!')

    #INFORMAÇÕES DOS DIRETÓRIOS
    toPathInfo = getStorageInfo(toPath)
    bufferInfo = getStorageInfo(buffer)

    filesToMove = getFilesToMove(fromPath)

    #VERIFICANDO SE EXISTE ARMAZENAMENTO DISPONIVEL
    if(filesToMove['totalSize'] > toPathInfo['free']):
      raise Exception(f"O diretório ({toPath}) não possui espaço suficiente!")
    elif(filesToMove['totalSize'] > bufferInfo['free']):
      raise Exception(f"O diretório ({buffer}) não possui espaço suficiente!")

    #COPIANDO E MOVENDO ARQUIVOS
    transferFiles(filesToMove['files'], fromPath, toPath, buffer)

  except Exception as e:
    logging.error(e)

with open('teste_script_backup.log', 'w') as log_file:
  log_file.write('')

logging.info(f"Caminhos\nfrompath: {os.getenv("FROMPATH")}\ntopath: {os.getenv("TOPATH")}\nbuffer: {os.getenv("BUFFER")}\n")
logging.info(f"Credenciais\nfrom_email: {os.getenv("FROM_EMAIL")}\nto_email: {os.getenv("TO_EMAIL")}\n")

createTestDirectory()


boot(os.getenv("FROMPATH"), os.getenv("TOPATH"), os.getenv("BUFFER"))