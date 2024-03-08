import os
from datetime import datetime, date
from shutil import disk_usage, move, copy2
import smtplib
from email.message import EmailMessage
import logging
from dotenv import load_dotenv

logging.basicConfig(filename='backup.log', level=logging.ERROR)

load_dotenv()

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

def emailMessage(data):

  message = ''

  if(data['status_type'] == 'error_path'):
    message = f"Não foi possivel realizar o backup.\n{data['error_message']}"
  
  else:
  
    if(data['status_type'] == 'error_file'):
      message = f"Houve um problema durante a transição de arquivos\n{data['error_message']}"

    elif(data['status_type']  == 'success'):
      message = f"Sucesso na transferência de arquivos."

    else:
      message = f"Houve um problema durante a transição de arquivos\n{data['error_message']}"
      return message

    generalDate = None
    
    #Mensagem com os dados da transferência de arquivos
    message += f"\n\nInformações sobre a transferência de arquivos:\n"
    message += f"Total de arquivos para transferência: {data['total_files']}\n"
    message += f"Total de arquivos transferidos: {len(data['moved_files'])}\n"
    message += f"Custo total de armazenamento: {convertBytesTo(data['total_size'])}\n\nArquivos Transferidos:\n"

    #Listando todos os arquivos movidos
    for file in data['moved_files']:

      if(generalDate != file['date'].date()):
        message += f"\n({file['date'].strftime('%d/%m/%Y')})\n"
        generalDate = file['date'].date()

      message += f"{file['name']} ({convertBytesTo(file['size'])})\n"
    
  return message

def sendEmail(movedFiles):

  try:

    body = emailMessage(movedFiles)

    #Montando o email
    msg = EmailMessage()
    msg['Subject'] = f"Rotina | Backup Semanal | ({datetime.now().strftime('%d/%m/%Y')})"
    msg['From'] = os.getenv("FROM_EMAIL")
    msg['To'] = os.getenv("TO_EMAIL")
    msg.set_content(body)

    #Enviando o email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
      smtp.login(os.getenv("FROM_EMAIL"), os.getenv("PASSWORD_EMAIL"))
      smtp.send_message(msg)

  except Exception as e:
    logging.error(e, datetime.now())

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
  currDate = datetime.today()
  fileInfoList = []

  for file in files:

    if(file.endswith('sql')):

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

    currDate = datetime.now()
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
    sendEmail(response)

def boot(fromPath, toPath, buffer):

  #EXECUTA O BACKUP APENAS NAS SEGUNDAS
  currDate = date.today()
  if(currDate.weekday() != 0):
    return

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
    logging.error(f"{e} ({currDate})")
    sendEmail({'status_type': 'error_path', 'error_message': e})


boot(os.getenv("FROMPATH"), os.getenv("TOPATH"), os.getenv("BUFFER"))