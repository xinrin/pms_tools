# vim: set fileencoding=utf-8
import re
import argparse
import os.path
import multiprocessing # for pyinstaller fixes
import sys

class Sm2Pms:

    def __init__(
        self,
        file: str,
        export="",
        file_content=None,
    ) -> None:
         with open(file) as f:
           contents = f.read()
           self.file_content = contents
           self.export = export
           self.bpm_changes = []
    
    def start(self):
        #get metada from sm file
        metadata = self.get_meta_data(self.file_content)
        #get all charts
        charts = self.get_charts(self.file_content)
        #get charts parsed on .pms and difficulty data from each chart
        pms_charts,charts_data = self.chart_structure_convert(charts,metadata)
        files_content = []
        #create file for each chart
        for pms_chart, chart_data in zip(pms_charts,charts_data):
            files_content.append(self.create_files(metadata,pms_chart, chart_data))

        # checking if the directory exist 
        if self.export is not None: 
          filepath = self.export
          if not os.path.isdir(self.export): 
              # not present then create it. 
              os.makedirs(self.export) 
        else:
            filepath = metadata["TITLE"] + "_convert"

        #create directory for default converts with no export paths
        if not os.path.isdir(filepath): 
          os.makedirs(filepath) 
         
        count = 0
        for file_content,chart_data in zip(files_content,charts_data):
            count = count + 1
            #create file name based on sm categorys and number of file
            file_name = metadata["TITLE"]+"_"+str(count)+"_" + chart_data["difficulty"]+".pms"
            final_path = os.path.join(filepath, file_name)
            #create file
            with open(final_path, 'w+') as f:
                f.write(file_content)
                f.close()
                print(final_path)


    def create_files(self,metadata,pms_chart,chart_data):
        self.bpm_changes = []
        file = []
        #header data
        file.append("*---------------------- HEADER FIELD")
        file.append("#PLAYER 2")
        file.append("#GENRE " + metadata["SUBTITLE"])
        file.append("#TITLE " + metadata["TITLE"])
        file.append("#ARTIST " + metadata["ARTIST"])
        file.append("#BPM " + metadata["BPMS"][0].split("=")[1])
        file.append("#PLAYLEVEL  " + chart_data["level"])
        #difficulty category convert
        diff_dict = {
          "Beginner": 1,
          "Easy": 2,
          "Medium": 3,
          "Hard": 4,
          "Challenge": 5,
          "Edit": 5,
        }
        diff_str = chart_data["difficulty"]
        #level
        file.append("#DIFFICULTY " + str(diff_dict.get(diff_str)))
        file.append("#LNTYPE  1")
        #background music
        file.append("#WAV02 " + metadata["MUSIC"])
        #WAV02 audio.mp3
        #bpm changes
        bpm_changes = [bpm.split("=")[1] for bpm in metadata["BPMS"]]
        #delete first element since is the base bpm
        bpm_changes.pop(0)
        counter = 1
        for i in range(len(bpm_changes)):
            #bpm atrributes based on hexbyte values, only if value more than 255
            #or float numbers
            if float(bpm_changes[i]) > 255 or (float(bpm_changes[i]).is_integer() == False):
             if (self.bpm_exist(bpm_changes[i]) == False):
               hex_string = '{:X}'.format(counter)
               file.append("#BPM"+hex_string.zfill(2)+" "+bpm_changes[i])
               self.save_bpm(bpm_changes[i])
               counter = counter + 1
                #stop values
        if(metadata["STOPS"][0] != ''):
          #stop values can change based on bpm, so we need to get sections
          #so we can get the current bpm
          stop_values = [stop.split("=")[1] for stop in metadata["STOPS"]]
          stop_section = [stop.split("=")[0] for stop in metadata["STOPS"]]
          for i in range(len(stop_values)):
            hex_string = '{:X}'.format(i+1)
            file.append("#STOP"+hex_string.zfill(2)+" "+str(round(self.seconds_to_snaps(stop_values[i],self.get_current_bpm_of_event(metadata,stop_section[i])))))

        file.append("*---------------------- MAIN DATA FIELD")
        text = ""

        pos_bgm,skip_sections,to_use = self.offset_to_section(metadata["OFFSET"],metadata["BPMS"][0].split("=")[1])
        
        #paste all the header stuff
        for part in file:
            text = text + part + "\n"


        #bgm keysound
        text = text + "#" + str(to_use).zfill(3) + "01:"+ pos_bgm +"\n"

        for event in pms_chart:
            text =  text + event 
        
        text = text + self.soflan_events(metadata,skip_sections)

        if(metadata["STOPS"][0] != ''):
            text = text + self.stop_events(metadata,skip_sections)

        return text

    def save_bpm(self,bpm):
        if bpm in self.bpm_changes:
          return 0
        self.bpm_changes.append(bpm)

    def get_bpm_point(self,bpm):
        if bpm in self.bpm_changes:
          for i in range(len(self.bpm_changes)):
           if(self.bpm_changes[i] == bpm):
             return '{:X}'.format(i+1)
        return 0

    def bpm_exist(self,bpm):
        if bpm in self.bpm_changes:
            return True
        return False
          


    def get_current_bpm_of_event(self,metadata,section):
        #bpm changes on file
        beats_sections = [float(bpm.split("=")[0]) for bpm in metadata["BPMS"]]
        soflan_values = [float(bpm.split("=")[1]) for bpm in metadata["BPMS"]]
        #delete first element since is the base bpm
        #beats_sections.pop(0)
        bpm = soflan_values[0]
        for beat_section,note_value in zip(beats_sections,soflan_values):
            if float(section) > beat_section:
                bpm = note_value
        return bpm


    def stop_events(self,metadata,skip_sections):
        events = ""
        #bpm changes on file
        beats_sections = [self.beat_to_section(float(stop.split("=")[0])) for stop in metadata["STOPS"]]
        stop_notes = [self.division_to_notes(float(stop.split("=")[0])) for stop in metadata["STOPS"]]

        for bt, sfl,i in zip(beats_sections, stop_notes,range(len(stop_notes))):
              hex_string = '{:X}'.format(i+1)
              events = events + "#"+str(bt+skip_sections).zfill(3) + "09" + ":" + sfl.replace("01", hex_string.zfill(2))  +"\n"
    
        return events

    def soflan_events(self,metadata,skip_sections):
        events = ""
        #bpm changes on file
        beats_sections = [self.beat_to_section(float(bpm.split("=")[0])) for bpm in metadata["BPMS"]]
        soflan_notes = [self.division_to_notes(float(bpm.split("=")[0])) for bpm in metadata["BPMS"]]
        bpm_changes = [bpm.split("=")[1] for bpm in metadata["BPMS"]]
        #delete first element since is the base bpm
        beats_sections.pop(0)
        soflan_notes.pop(0)
        bpm_changes.pop(0)

        for bt, sfl,i,bpm_value in zip(beats_sections, soflan_notes,range(len(soflan_notes)),bpm_changes):
              if (float(bpm_value) > 255) or (float(bpm_value).is_integer() == False):
               point = self.get_bpm_point(bpm_value)
               events = events + "#"+str(bt+skip_sections).zfill(3) + "08" + ":" + sfl.replace("01", point.zfill(2))  +"\n"
              else:
                hex_string = '{:X}'.format(int(float(bpm_value)))
                events = events + "#"+str(bt+skip_sections).zfill(3) + "03" + ":" + sfl.replace("01", hex_string.zfill(2))  +"\n"
    
        return events

    def get_meta_data(self,content):
        re.findall(r'#TITLE:(.*?);', content)

        # a Python object (dict):
        data = {
          "TITLE": re.findall(r'#TITLE:(.*?);', content)[0],
          "SUBTITLE": re.findall(r'#SUBTITLE:(.*?);', content)[0],
          "ARTIST": re.findall(r'#ARTIST:(.*?);', content)[0],
          "MUSIC": re.findall(r'#MUSIC:(.*?);', content)[0],
          "OFFSET": re.findall(r'#OFFSET:(.*?);', content)[0],
          "BPMS": re.findall(r'#BPMS:(.*?);', content,flags=re.S)[0].split("\n,"),
          "STOPS": re.findall(r'#STOPS:(.*?);', content,flags=re.S)[0].split("\n,"),
        }
        return data
    
    def get_charts(self,content):
        return re.findall(r'#NOTES:\n     popn:(.*?);', content,flags=re.S)

    
    def beat_to_section(self,beat):
        return int((beat//4))

    #get notes based on the divison notes of arrowvortex
    def division_to_notes(self,div):
        value = ""
        note = round(((div/4)-(div//4))*192)
        for i in range(192):
            if i == note:
                value = value + "01"
            else:
                value = value + "00"
        return value

    def seconds_to_snaps(self,seconds,bpm):
        time_per_section = self.time_per_section(bpm)
        return float(((float(seconds)*192)/time_per_section))

    def time_per_section(self,bpm):
        return (float((60/float(bpm))*4))

    def offset_to_section(self,offset,bpm):
        time_per_section = self.time_per_section(bpm)
        pos = 0
        skip_sections = 0
        sections_to_use = 0
        #if offset is negative, calculate sections to skip
        if float(offset) < 0:
         pos = (((float(offset)*-1)*192)/time_per_section)
         temp_pos = pos
         skip_sections = 1
         while temp_pos >= 192:
             temp_pos = temp_pos - 192
             skip_sections  = skip_sections  + 1
         #substraction of last section
         pos = 192 - temp_pos 
        else: 
         pos = ((float(offset)*192)/time_per_section)
         temp_pos = pos
         sections_to_use = 0
         while temp_pos >= 192:
             temp_pos = temp_pos - 192
             sections_to_use  = sections_to_use  + 1
         pos = temp_pos

        
        #convert as note notation
        
        value = ""
        for i in range(192):
            if i == int(pos):
                value = value + "02"
            else:
                value = value + "00"
        return(value,skip_sections,sections_to_use)
          

    

    def chart_structure_convert(self,charts,metadata):

        #handle offset
        pos_bgm,skip_sections,to_use = self.offset_to_section(metadata["OFFSET"],metadata["BPMS"][0].split("=")[1])
        
        parsed = []
        difficulties = []
        for chart in charts:
            splited_chart = chart.split(":")
            #get data of each chart
            chart_data = {
              "difficulty": splited_chart[1].replace('\n', '').replace(' ', ''),
              "level": splited_chart[2].replace('\n', '').replace(' ', ''),
             }
            splited_chart = splited_chart[len(splited_chart)-1].split(",\n")
            splited_chart = list(filter(lambda x: len(x) > 0, splited_chart))
            section_count=skip_sections#
            events = []
            #parse chart stuff
            for section in splited_chart:
                splited_section = section.split("\n")
                splited_section = list(filter(lambda x: len(x) > 0, splited_section))
                events.append(self.notes_array_to_pms_type(splited_section,section_count))
                section_count = section_count + 1
            parsed.append(events)
            difficulties.append(chart_data)

        return parsed,difficulties

    
    def notes_array_to_pms_type(self,array,count):
        events = ""
        btns = ["11","12","13","14","15","22","23","24","25"]
        btns_hld = ["51","52","53","54","55","62","63","64","65"]
        lns = [""] * 9
        for part in array:
         #convert 0 to -> 0(number)
            for i in range(9):
                if(part[i] == "0"):
                    lns[i] = lns[i] +"00" 
                else:
                    lns[i] = lns[i] +"0" + part[i]  
        for btn, ln,btn_hld in zip(btns, lns,btns_hld):
            #hold notes
            if ('2' in ln) or ('3' in ln):
               normal_ln = ln
               hold_ln = ln
               if '1' in normal_ln.replace('2', '0').replace('3', '0'):
                events = events + "#"+str(count).zfill(3) + btn + ":" + normal_ln.replace('2', '0').replace('3', '0') +"\n"
               events = events + "#"+str(count).zfill(3) + btn_hld + ":" + hold_ln.replace('1', '0').replace('3', '1').replace('2', '1') +"\n"
              #normal line type
            elif '1' in ln:
              events = events + "#"+str(count).zfill(3) + btn + ":" + ln +"\n"
        return events
            


        

if __name__ == "__main__":
    multiprocessing.freeze_support() # pyinstaller
    parser = argparse.ArgumentParser(description='Parse .sm files to .pms')
    parser.add_argument(
        '--file',
        dest='file',
        action='store',
        type=str,
        required=True,
        help='The file name to export.',
    )
    parser.add_argument(
        '--export',
        dest='export',
        action='store',
        type=str,
        help='Path were exported files will be save.',
    )
    #print(sys.argv)
    
    # Parse args, validate invariants.
    
    if len(sys.argv) != 2:
     args = parser.parse_args()
     file = args.file
     export = args.export
    else:
     file = sys.argv[1]
     export = None
     
    
    if os.path.isfile(file):
      export = Sm2Pms(file,export)
      export.start()
    else:
        raise Exception('File doesnt exist!')

