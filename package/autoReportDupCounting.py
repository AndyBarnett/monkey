#!/usr/bin/python2

import os
import re
import sys
import datetime
import smtplib
import HTML
from fogbugz import FogBugz
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from ConfigParser import SafeConfigParser

files=[]

def main():
    
        if len(sys.argv) != 3:  
            sys.exit("Incorrect number of arguments")
            
        c = readcFile(sys.argv[1])
        
        c['test.build']=sys.argv[2]
        rawCrashes = getCrashesFromDirectory(c['test.separator'], c['test.dir'])
        crashes = parseCrashes(rawCrashes, c)
        
        if (len(crashes) != 0):
                         
            fb = FogBugz(c['fogbugz.url'])
            fogbugzQuery='project:\"' + c['fogbugz.project'] + '"'
            fb.logon(c['fogbugz.user'], c['fogbugz.pass'])
            fogBugzResp = fb.search(q=fogbugzQuery,cols='ixBug,sTitle,fOpen,events')
            crashes = flagExcludeList(c, crashes)
            crashes = flagFBDuplicates(fogBugzResp, crashes, c)
            logCrashesToFogbugz(fb, c, crashes)
            
        emailReport(c, crashes)
        
        print 'Done'

def readcFile(fileName):
    
    cFile={}
          
    parser = SafeConfigParser()
    parser.read(fileName)
    
    cFile['fogbugz.user'] = parser.get('fogbugz', 'user')
    cFile['fogbugz.pass'] = parser.get('fogbugz', 'pass')
    cFile['fogbugz.url'] = parser.get('fogbugz', 'url')
    cFile['fogbugz.project'] = parser.get('fogbugz', 'project')
    cFile['gmail.user'] = parser.get('gmail', 'user')
    cFile['gmail.pass'] = parser.get('gmail', 'pass')
    cFile['gmail.to'] = parser.get('gmail', 'to')
    cFile['gmail.from'] = parser.get('gmail', 'from')
    cFile['test.dir'] = parser.get('test', 'dir')
    cFile['test.separator'] = parser.get('test', 'separator')
    cFile['test.exclude'] = parser.get('test', 'exclude')
    #cFile['test.replace[0]'] = parser.get('test', 'test.replace[0]')
    #cFile['test.replaceWith[0]'] = parser.get('test', 'test.replaceWith[0]')
    cFile['replace.replace'] = parser.get('replace', 'replace')
    cFile['replace.replaceWith'] = parser.get('replace', 'replaceWith')
    
    #print cFile["test.dir"]
    #print cFile["replace.replace"]
    #print cFile["replace.replaceWith"]
    #print cFile['test.replaceWith[0]']
    
    return dict(cFile)

def getCrashesFromDirectory(separator, directory):
    
    crashes=[]
    
    for fileName in os.listdir(directory):
        if ".log" in fileName:
            theFile = open(directory + "/" + fileName)
            files.append(fileName);
            print 'Found file: ' +  directory + "\\" + fileName + '\n'
            crashes = crashes + theFile.read().replace('\r\n', '\n').split(separator)
            theFile.close()
            
    print "Found " + str(len(crashes)) + ' potential crashes\n'
            
    return crashes

def parseCrashes(rawCrashes, c):

    crashDict={}    
    crashesList=[]
    
    replaceList=[]
    replaceWithList=[]
    dups=0

    replaceList.extend(c['replace.replace'].split('\n'))
    replaceWithList.extend(c['replace.replaceWith'].split('\n'))
    
    for rawCrash in rawCrashes:
        
        rawCrash = str(rawCrash).strip() 
        #rawCrash = re.sub(r'    // activityResuming(com.sec.android.app.twlauncher)', "",rawCrash)
        
        if rawCrash:
            matchShortMsg =  re.search('// Short Msg: .*\n', rawCrash)
            matchLongMsg =  re.search('// Long Msg: .*\n', rawCrash)
            matchBuildLbl =  re.search('// Build Label: .*\n', rawCrash)
            matchBodyStart = re.search('// Build Time: \d*\n', rawCrash)
            matchBodyEnd = re.search('// \n', rawCrash)
            matchTime = re.search('elapsed time=\d+ms', rawCrash)
            matchNetwork = re.search('## Network stats: .*\n', rawCrash)
            
            if matchShortMsg and matchLongMsg and matchBuildLbl and matchBodyStart and matchBodyEnd and matchTime:
                
                #valid data
                
                crashDict['skip'] = 'false'
                crashDict['logged'] = 'false'
                                
                shortMessage = str(matchShortMsg.group()).strip().replace('// Short Msg: ', '')
                longMessage = str(matchLongMsg.group()).strip().replace('// Long Msg: ', '')[:128]
                    
                buildLabel = str(matchBuildLbl.group()).strip().replace('// Build Label: ', '')
                desc = str(rawCrash[matchBodyStart.end():matchBodyEnd.start()]).strip()
                formattedDesc = re.sub(r'java:\d*\)', "java:\)",desc)

                elapsedTime = (re.search('\d+',matchTime.group())).group()
                network = str(matchNetwork.group()).strip()
                raw = rawCrash.strip()
                
                #flag duplicate errors   
                thisLongMessage = longMessage             
                for i in range(len(replaceList)):
                    thisLongMessage = re.sub(replaceList[i],replaceWithList[i],thisLongMessage)
                    
                thisDesc = formattedDesc
                for i in range(len(replaceList)):
                    thisDesc = re.sub(replaceList[i],replaceWithList[i],thisDesc)
                    
                for addedCrash in crashesList:
                    formattedAddedCrashDesc = re.sub(r'java:\d*\)', "java:\)",addedCrash['desc'])
                    formattedAddedCrashTitle = re.sub(r'java:\d*\)', "java:\)",addedCrash['longMessage'])
                    
                    for i in range(len(replaceList)):
                        formattedAddedCrashTitle = re.sub(replaceList[i],replaceWithList[i],formattedAddedCrashTitle)
                        
                    for i in range(len(replaceList)):
                        formattedAddedCrashDesc = re.sub(replaceList[i],replaceWithList[i],formattedAddedCrashDesc)
                    
                    if formattedAddedCrashTitle == thisLongMessage and formattedAddedCrashDesc == thisDesc:
                        crashDict['skip'] = 'true'
                        crashDict['skipDesc'] = 'Duplicate found in log file'
                        #print "duplicate found in log file: "+addedCrash['longMessage']
                                                    
                crashDict['shortMessage'] = shortMessage
                crashDict['longMessage'] = longMessage
                crashDict['buildLabel'] = buildLabel
                crashDict['desc'] = desc
                crashDict['elapsedTime'] = elapsedTime
                crashDict['network'] = network
                crashDict['raw'] = raw
                        
                crashesList.append(dict(crashDict))
                
    print 'Valid crashes found [including duplicates] ' + str(len(crashesList)) + '\n' 
    
    return crashesList

def flagExcludeList(c, crashes):
    
    if str(c['test.exclude']).strip() !='':
        
        #print 'Flagging Exclude list: ' + c['replace.replace'] + '\n'
            
        excludeList = str(c['test.exclude']).split(';')
        
        count=0
        for item in excludeList:
            for crash in crashes:
                crash['closed'] = 'unknown'
                if (str(crash['longMessage']).find(item) > -1)  or  (str(crash['desc']).find(item) > -1):
                    crash['skip'] = 'true'
                    crash['skipDesc'] = 'Exclusion string: \'' + item + '\' found'
                    count += 1
                        
        print 'Excludes found: ' + str(count) + '\n'
                      
    return crashes

        
def flagFBDuplicates(fogBugzResp, crashes, c):
    
    print 'Flagging FOGBUGZ duplicates\n'
    
    replaceList=[]
    replaceWithList=[]

    replaceList.extend(c['replace.replace'].split('\n'))
    replaceWithList.extend(c['replace.replaceWith'].split('\n'))
    
    for crash in crashes:
        
        if crash['skip'] == 'false': #don't check Fogbugz if we have a file duplicate
                  
            for case in fogBugzResp.cases.findAll('case'):
                
                fbTitle=str(case.stitle.string.encode('UTF-8')).strip()
                fbixbug=case.ixbug.string
                fbDesc=case.events.event.s.string
                fbOpenStatus=case.fopen.string
                
                fbFormattedDesc = re.sub(r'\s+', '', str(fbDesc))
                fbFormattedDesc = re.sub(r'java:\d*\)', "java:)",str(fbFormattedDesc))
                
                fbFormattedDesc = str(fbFormattedDesc).replace('<![CDATA[', '')
                fbFormattedDesc = str(fbFormattedDesc).replace(']]>', '')
                
                formattedDesc = re.sub(r'java:\d*\)', "java:)",  str(crash['desc']))
                formattedDesc = re.sub(r'\s+', '', formattedDesc)
                
                for i in range(len(replaceList)):
                    fbTitle = re.sub(replaceList[i],replaceWithList[i],fbTitle)
                
                for i in range(len(replaceList)):
                    fbFormattedDesc = re.sub(replaceList[i],replaceWithList[i],fbFormattedDesc)

                for i in range(len(replaceList)):
                    formattedLongMessage = re.sub(replaceList[i],replaceWithList[i], str(crash['longMessage']))
                formattedLongMessage = formattedLongMessage.strip()
                
                for i in range(len(replaceList)):
                    formattedDesc = re.sub(replaceList[i],replaceWithList[i],formattedDesc)
                formattedDesc = formattedDesc.strip()
                #print "formatted desc = "+formattedDesc
                
                if formattedLongMessage == fbTitle:
                    print "matched formattedLongMessage and fbTitle: "+ formattedLongMessage + "--------" + fbTitle
                    print "fbFormattedDesc and formattedDesc are:\n" + fbFormattedDesc + "\n" + formattedDesc +"\n\n"
                    if str(fbFormattedDesc).find(str(formattedDesc)) > -1:
                        if str(fbOpenStatus)=='true':
                            #print "found an open match"
                            crash['skip'] = 'true'
                            crash['skipDesc'] = 'Open duplicate found in Fogbugz'
                            #break
                        if str(fbOpenStatus)=='false':
                            #print "found a closed match"
                            crash['closed'] = 'true'
                            crash['closedNumber'] = str(fbixbug)
                            #break
    return crashes
  
def logCrashesToFogbugz(fb, c, crashes):
    
    for crash in crashes:
        
        if crash['skip'] == 'false' and crash['closed'] == 'unknown':
            print 'LOGGING:'
            print crash['longMessage']
            print "\n"
            
            resp = fb.new(sTitle=crash['longMessage'],sEvent=crash['desc'],sProject=c['fogbugz.project'])
                        
            for case in resp.findAll('case'):
                crash['ixbug']=case['ixbug']
                crash['logged']='true'
           
    for crash in crashes:
        if crash['skip'] == 'true':   
            print 'SKIPPING: ' + crash['skipDesc']
            print crash['longMessage']
            
    for crash in crashes:
        if crash['closed'] == 'true':
            #print "crash['closednumber'] = "+crash['closedNumber']
            fb.reopen(ixbug=crash['closedNumber'])
            print 'REOPENING '+crash['longMessage']+", Bug "+crash['closedNumber']
            
    return crashes

def averageTime(crashes):
    
    allTimes=0
    for crash in crashes:
        allTimes += int(crash['elapsedTime'])
    if(allTimes != 0):
        allTimes = allTimes/(len(crashes))
            
    return allTimes
 
      
def emailReport(c, crashes):
    
    loggedCount=0
    skipCount=0
    reopenedCount=0
               
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Android monkey stress test report [' + c['test.build'] + ' ]'
    msg['From'] =  c['gmail.from']
    msg['To'] = c['gmail.to']
    
    for crash in crashes:
        if crash['logged'] == 'true':
            loggedCount+=1
        if crash['skip'] == 'true':
            skipCount+=1
        if crash['closed'] == 'true':
            reopenedCount+=1
        
    print 'Making report\n'    
    
    rootTable = HTML.Table(style='text-align:left;border-collapse:collapse;', width='100%')
    rootTable.rows.append(['Date',datetime.datetime.now().strftime("%d/%m/%y")])
    #rootTable.rows.append(['Build', c['test.build']])
    rootTable.rows.append(['Bugs logged', str(loggedCount)])
    rootTable.rows.append(['Bugs reopened', str(reopenedCount)])
    rootTable.rows.append(['Duplicates', str(skipCount)])
    rootTable.rows.append(['Total', str(len(crashes))])
    rootTable.rows.append(['Fogbugz Project', c['fogbugz.project']])
    rootTable.rows.append(['Test directory', c['test.dir']])
    for logFile in files:
        rootTable.rows.append(['Log file', logFile])
        
    if (len(crashes) > 0):    
        averageRunningTime = averageTime(crashes)    
        s, ms = divmod(averageRunningTime, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        rootTable.rows.append(['Average running time',  "%d:%02d:%02d" % (h, m, s)])    
                   
    allLoggedTable = HTML.Table(header_row=['Logged ' + str(loggedCount) + ' crashes to ' + c['fogbugz.project']],
                                style='text-align:left;border-collapse:collapse;', width='100%')
    allSkippedTable = HTML.Table(header_row=['Skipped ' + str(skipCount) + ' issues'],
                                style='text-align:left;border-collapse:collapse;', width='100%')
    allReopenedTable = HTML.Table(header_row=['Reopened ' + str(reopenedCount) + ' issues'],
                                style='text-align:left;border-collapse:collapse;', width='100%')
    for crash in crashes:
        longMsg=crash['longMessage']
        crashItemTable = HTML.Table(header_row=['Title', longMsg], 
                                    style='text-align:left;border-collapse:collapse;white-space:pre-line;', width='100%')
        replacedDesc=re.sub('\n','<br/>',crash['desc'])
        if crash['logged'] == 'true':
            crashItemTable.rows.append(['Bug #', crash['ixbug']])
            itemURL = c['fogbugz.url'] + 'default.asp?' + crash['ixbug']
            HTML.link(c['fogbugz.url'], c['fogbugz.url'])
            crashItemTable.rows.append(['Bug URL', itemURL])
            crashItemTable.rows.append(['Build Label', crash['buildLabel']])
            crashItemTable.rows.append(['Description', replacedDesc])
            crashItemTable.rows.append(['Network', crash['network']])
            crashItemTable.rows.append(['Elapsed Time', crash['elapsedTime'] + 'ms'])
            allLoggedTable.rows.append([crashItemTable])
        if crash['skip'] == 'true':
            crashItemTable.rows.append(['Skip Reason', crash['skipDesc']])
            crashItemTable.rows.append(['Build Label', crash['buildLabel']])
            crashItemTable.rows.append(['Description', replacedDesc])
            crashItemTable.rows.append(['Network', crash['network']])
            crashItemTable.rows.append(['Elapsed Time', crash['elapsedTime'] + 'ms'])
            allSkippedTable.rows.append([crashItemTable])
        if crash['closed'] == 'true':
            crashItemTable.rows.append(['Bug #', crash['closedNumber']])
            itemURL = c['fogbugz.url'] + 'default.asp?' + crash['closedNumber']
            HTML.link(c['fogbugz.url'], c['fogbugz.url'])
            crashItemTable.rows.append(['Build Label', crash['buildLabel']])
            crashItemTable.rows.append(['Description', crash['desc']])
            allReopenedTable.rows.append([crashItemTable])
    
    rootTable.rows.append(['Crashes', str(allLoggedTable)])
    rootTable.rows.append(['Reopened', str(allReopenedTable)])
    rootTable.rows.append(['Duplicates', str(allSkippedTable)])
    
    #crashItemTable.rows.append(['Bug URL', itemURL])
                
    html = str(rootTable)
    msg.attach(MIMEText(html,'html'))
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login(c['gmail.user'], c['gmail.pass'])
    
    print "Emailing report\n" 
    
    server.sendmail(c['gmail.from'], c['gmail.to'], msg.as_string())
    server.quit()
        
main()  
