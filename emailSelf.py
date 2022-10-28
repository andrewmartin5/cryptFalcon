import win32com.client as win32

def emailSelf():
	outlook = win32.Dispatch('outlook.application')
	mail = outlook.CreateItem(0)
	mail.Subject = "Donaroo"
	mail.To = "6039300523@txt.att.net"
	mail.Send()

if __name__ == "__main__":
	emailSelf()