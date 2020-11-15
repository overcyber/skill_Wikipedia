from mediawikiapi import MediaWikiAPI

from core.base.model.Intent import Intent
from core.base.model.AliceSkill import AliceSkill
from core.dialog.model.DialogSession import DialogSession
from core.util.Decorators import IntentHandler, Online


class Wikipedia(AliceSkill):
	"""
	Author: Psychokiller1888
	Description: Allows one to find informations about a topic on wikipedia
	"""


	def __init__(self):
		self._resultSummary = ""
		self._top5Results = list()
		self._alternatveResultUsed = False
		self._devDebug = False
		super().__init__()


	@staticmethod
	def _extractSearchWord(session: DialogSession) -> str:
		if 'Letters' in session.slots:
			return ''.join([slot.value['value'] for slot in session.slotsAsObjects['Letters']])
		return session.slots.get('What', session.slots.get('RandomWord'))


	def _whatToSearch(self, session: DialogSession, question: str):
		search = self._extractSearchWord(session)
		self.continueDialog(
			sessionId=session.sessionId,
			text=self.randomTalk(text=question, replace=[search]),
			intentFilter=[Intent('UserRandomAnswer')],  # Intent('SpellWord')],
			currentDialogState='whatToSearch',
			probabilityThreshold=0.01
		)


	@IntentHandler('DoSearch')
	@IntentHandler('UserRandomAnswer', requiredState='whatToSearch')
	@IntentHandler('SpellWord', requiredState='whatToSearch')
	@Online
	def searchIntent(self, session: DialogSession):
		if 'UserRandomAnswer' in session.intentName:
			search = session.payload['input']
		else:
			search = self._extractSearchWord(session)

		if not search:
			self._whatToSearch(session, 'whatToSearch')
			return

		mediawikiapi = MediaWikiAPI()
		# set language of the results
		mediawikiapi.config.language = self.LanguageManager.activeLanguage

		# Debug code for dev
		if self._devDebug:
			self.logInfo(f'User request = {search}')

		# Store the top 5 titles of the requested search (5 reduces chances of index error)
		self._top5Results = mediawikiapi.search(search, results=5)
		# set a index value for iterating through a list in the dialogs
		index = 0

		if not self._top5Results:
			self.logWarning('No match')
			self._whatToSearch(session, 'noMatch')
			return

		# remove known ambiguous results
		self.removeKnowenAmbiguousResults()

		# Check for exceptions and return any good result
		self._resultSummary = self.sortThroughResults(wikiInstance=mediawikiapi, index=index)

		# If there are bo good answers then log a warning and inform user
		if not self._resultSummary:
			self.logWarning('No match')
			self._whatToSearch(session, 'noMatch')

		# If search result found say the result and end
		else:
			if self._devDebug:
				self.logInfo(f'result Summary is {self._resultSummary}')

			if not self._alternatveResultUsed:
				self.sayResult(session=session, index=index)
			else:
				self.sayAlternatives(alternatives=self._top5Results[index + 1])
				self.sayResult(session=session, index=index)


	def removeKnowenAmbiguousResults(self):
		"""Remove knowen ambiguos results and leave potential results"""

		for item in self._top5Results:
			if '(disambiguation)' in item:
				self._top5Results.remove(item)
		if self._devDebug:
			self.logInfo(f'Top 5 results = {self._top5Results}')
			self.logInfo("")


	def sortThroughResults(self, wikiInstance, index):
		""" Search through summary's, remove results that may cause error and return good result"""
		errorMsg = ""
		resultSummary = ""

		while index <= 4:
			try:
				resultSummary = wikiInstance.summary(self._top5Results[index], sentences=self.getConfig('maxSentences'))
			except Exception as e:
				errorMsg = str(e)
			finally:
				if 'may refer to' in resultSummary or 'Try another id' in errorMsg:
					self._alternatveResultUsed = True
					index += 1
				else:
					index = 5

		if errorMsg:
			self.logWarning(f'Skipping over this error message >> "{errorMsg}"... searching for alternatives ')

		return resultSummary


	def sayAlternatives(self, alternatives: str):
		"""Tell user a alternative search"""
		self.say(
			text=self.randomTalk(text="dialogMessage1", replace=[alternatives]),
			canBeEnqueued=False
		)


	def sayResult(self, session, index):
		self.say(
			text=self._resultSummary
		)
		self.endSession(sessionId=session.sessionId)

		if self._alternatveResultUsed:
			index += 2

		index += 1

		if index <= len(self._top5Results):
			message = f'You may also be interested in {self._top5Results[index]}'
			self.ThreadManager.doLater(
				interval=3,
				func=self.delayedSayMessage,
				kwargs={'message': message}
			)

		self._resetObjects()


	def _resetObjects(self):
		self._resultSummary = ""
		self._top5Results = list()
		self._alternatveResultUsed = False


	def delayedSayMessage(self, message):
		self.say(
			text=message
		)
