import atexit
import os


class SingletonInstance:
	def __init__(self, lock_file):
		self.lock_file = lock_file
		self.lock_handle = None

	def acquire(self):
		"""Return True if lock was acquired, False otherwise."""
		if os.path.exists(self.lock_file):
			return False
		self.lock_handle = open(self.lock_file, 'w')
		try:
			self.lock_handle.write(str(os.getpid()))
			self.lock_handle.flush()
		except Exception:
			self.release()
			return False
		atexit.register(self.release)
		return True

	def release(self):
		"""Release the lock."""
		if self.lock_handle:
			try:
				self.lock_handle.close()
			except Exception:
				pass
			try:
				os.remove(self.lock_file)
			except Exception:
				pass

	def get_existing_pid(self):
		"""Return the PID of the existing lock file, or None if it doesn't exist."""
		if os.path.exists(self.lock_file):
			with open(self.lock_file, 'r') as f:
				return int(f.read().strip())
		return None
