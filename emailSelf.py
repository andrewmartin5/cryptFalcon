try:
	import win32com.client as win32
except:
	pass

def emailSelf():
	try:
		outlook = win32.Dispatch('outlook.application')
		mail = outlook.CreateItem(0)
		mail.Subject = "Donaroo"
		mail.To = "6039300523@txt.att.net"
		mail.Send()
	except:
		pass

if __name__ == "__main__":
	emailSelf()