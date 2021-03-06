bl_info = {
    "name" : "VSE letterboxing",
    "description": "A menu for adding letterboxes to VSE strips that don't have the exact same aspect ratio as the scene",
    "author" : "Robert Forsman <blender@thoth.purplefrog.com>",
    "version": (0,1),
    "blender": (2,71,0),
    "location": "Video Sequence Editor > Strip > Letterbox",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Sequencer/Letterbox",
    "category": "Sequencer",
}

#
# Thanks to Genome36 for feedback and help


import bpy


class SequencerLetterboxMenu(bpy.types.Menu):
    bl_idname = "SEQUENCER_MT_strip_letterbox"
    bl_label = "Letterbox"

    def draw(self, ctx):

        layout = self.layout

        # default operator will keep whatever alignment was last used
        props = layout.operator(SequencerLetterbox.bl_idname, text=SequencerLetterbox.bl_label)
        props.strip_DAR=0 #operator should compute fresh value

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox Center")
        props.align_x=0.5
        props.align_y=0.5
        props.strip_DAR=0 #operator should compute fresh value

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox East")
        props.align_x=0
        props.align_y=0.5
        props.strip_DAR=0

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox West")
        props.align_x=1
        props.align_y=0.5
        props.strip_DAR=0

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox North")
        props.align_x=0.5
        props.align_y=0
        props.strip_DAR=0

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox South")
        props.align_x=0.5
        props.align_y=1
        props.strip_DAR=0



class SequencerLetterboxArbitrary:

    @classmethod
    def letterbox_arbitrary_op(cls, scene, align_x=0.5, align_y=0.5, strip_DAR=0.0):

        malfunction, xform, strip_DAR = SequencerLetterboxArbitrary.letterbox_arbitrary(scene.sequence_editor.active_strip, scene, align_x, align_y, strip_DAR)
        if malfunction:
            return malfunction, None, None

        for strip in scene.sequence_editor.sequences:
            strip.select = ( strip == xform )
        scene.sequence_editor.active_strip = xform

        return False, xform, strip_DAR

    @classmethod
    def scene_pixel_aspect(cls, scene):
        return scene.render.pixel_aspect_x / scene.render.pixel_aspect_y

    @classmethod
    def compute_scale_from_aspect_ratios(cls, scene_aspect_ratio, source_aspect_ratio):
        if scene_aspect_ratio > source_aspect_ratio:
            # wider
            scale_x = source_aspect_ratio / scene_aspect_ratio
            scale_y = 1
        else:
            scale_x = 1
            scale_y = scene_aspect_ratio / source_aspect_ratio
        return scale_x, scale_y

    @classmethod
    def compute_strip_display_aspect_ratio(cls, src_strip):
        if src_strip.type == 'SCENE':
            # this is a Scene strip, or something close enough.
            base_width = src_strip.scene.render.resolution_x
            base_height = src_strip.scene.render.resolution_y
        elif src_strip.type == 'IMAGE' or src_strip.type=='MOVIE':
            base_width = src_strip.elements[0].orig_width
            base_height = src_strip.elements[0].orig_height
        elif hasattr(src_strip, "input_1"):
            # I am not adding an if clause for every effect strip
            return cls.compute_strip_display_aspect_ratio(src_strip.input_1)
        else:
            return "unable to compute display aspect ratio for %s strip"%src_strip.type, None

        if (base_width is None or base_height is None):
            msg = "Unable to determine width&height of base strip.  "
            if (src_strip.type == "IMAGE" or src_strip.type == "MOVIE"):
                msg = msg + "blender was too lazy to parse them from the source media?"
            else:
                msg = msg + "Strip was " + src_strip.type + " instead of IMAGE or MOVIE."
            return msg, None

        # this next bit is wrong for DVDs (and CableLabs VoD and anything else with non-square pixels)
        # but blender isn't smart enough to extract it from the source media
        if hasattr(src_strip, "orig_display_aspect_ratio") and 0 != src_strip.orig_display_aspect_ratio:
            source_PAR = src_strip.orig_display_aspect_ratio * base_height / base_width
            source_aspect_ratio = src_strip.orig_display_aspect_ratio
        else:
            if src_strip.type == 'SCENE':
                source_PAR = cls.scene_pixel_aspect(src_strip.scene)
            elif hasattr(src_strip, "orig_pixel_aspect_ratio") and 0 != src_strip.orig_pixel_aspect_ratio:
                source_PAR = src_strip.orig_pixel_aspect_ratio
            else:
                source_PAR = 1
            source_aspect_ratio = base_width * source_PAR / base_height
        return False, source_aspect_ratio

    @classmethod
    def compute_scene_display_aspect_ratio(cls, scene):
        scene_PAR = cls.scene_pixel_aspect(scene)
        scene_width = scene.render.resolution_x
        scene_height = scene.render.resolution_y
        scene_aspect_ratio = scene_PAR * scene_width / scene_height
        return scene_aspect_ratio

    @classmethod
    def compute_scale(cls, strip_DAR, scene):

        return cls.compute_scale_from_aspect_ratios(cls.compute_scene_display_aspect_ratio(scene), strip_DAR)

    @classmethod
    def letterbox_arbitrary(cls, strip, scene, align_x=0.5, align_y=0.5, strip_DAR=0.0):
        """
        :param strip: what is our target strip?  It can be a Transform strip of a Scene, Image, or Movie strip; or it can be the Scene, Image, or Movie and the Transform will be located or created.
        :param scene: the Scene the target strip lives in (used to figure out the scene resolution)
        :param align_x:
        :param align_y:
        :return:
        """

        if strip is None:
            return "You have not selected an action strip to letterbox", None, None

        if 0==strip_DAR:
            malfunction, strip_DAR = cls.compute_strip_display_aspect_ratio(strip)
            print([ malfunction, strip_DAR])
            if malfunction:
                # I don't like this style of code, but it is in fashion
                return malfunction, None, None

        scale_x, scale_y = cls.compute_scale(strip_DAR, scene)

        if (strip.type == 'TRANSFORM'):
            xform = strip
        else :
            xform = SequencerLetterboxArbitrary.transform_strip_for(strip, scene)

        src_strip = xform.input_1

        if (scale_x != scale_y):
            xform.use_uniform_scale = False

        xform.scale_start_x = scale_x
        xform.scale_start_y = scale_y

        #print(scene.render.resolution_x*(1-scale_x))

        xlate_x = scene.render.resolution_x * (1 - scale_x) * (align_x - 0.5)
        xlate_y = scene.render.resolution_y * (1 - scale_y) * (align_y - 0.5)

        if (xform.translation_unit=='PIXELS'):
            xform.translate_start_x = xlate_x
            xform.translate_start_y = xlate_y
        else:
            xform.translate_start_x = 100 * xlate_x / scene.render.resolution_x
            xform.translate_start_y = 100 * xlate_y / scene.render.resolution_y

        # I don't feel like adding extra code to handle the Image Offset checkbox just yet.
        src_strip.use_translation = False
        if (src_strip.use_translation):
            print("python, you fail at booleans (%r)"%src_strip.use_translation)
            src_strip.use_translation = 0
            print(src_strip.use_translation)

        return False, xform, strip_DAR

    @classmethod
    def transform_strip_for(cls, other_strip, scene):
        for strip in scene.sequence_editor.sequences_all:
            if strip.type == 'TRANSFORM' and strip.input_1 == other_strip:
                return strip
        ch = other_strip.channel+1
        s = other_strip.frame_start
        e = s + other_strip.frame_final_duration - 1

        if other_strip.type=='SOUND':
            raise ValueError("you can not letterbox Sound strips")

        #print("%d, %d"%(s,e))
        effect = scene.sequence_editor.sequences.new_effect("Letterbox", 'TRANSFORM', ch, s, frame_end=e,
                                                            seq1=other_strip)
        # because somehow setting frame_end in the previous method call accomplishes nothing
        effect.update()

        effect.blend_type = 'ALPHA_OVER'

        return effect


#


class SequencerLetterbox(bpy.types.Operator):
    """Add or adjust the transform effect on a strip to put letterboxes on the left and right or top and bottom to center the content and preserve its original aspect ratio"""
    bl_idname = "sequencer.letterbox_center"
    bl_label = "Letterbox"
    bl_options = {'REGISTER', 'UNDO'}

    align_x = bpy.props.FloatProperty(name="Align X", default=0.5, min=0, max=1.0,
                                      subtype='FACTOR', precision=4, step=100,
                                      description="horizontal alignment of the content.  0.0 for left; 1.0 for right; 0.5 for centered")
    align_y = bpy.props.FloatProperty(name="Align Y", default=0.5, min=0, max=1.0,
                                      subtype='FACTOR', precision=4, step=100,
                                      description="vertical alignment of the content.  0.0 for top; 1.0 for bottom; 0.5 for centered")
    strip_DAR = bpy.props.FloatProperty(name="Strip display aspect ratio", default=0.0, min=0, max=100,
                                        subtype='FACTOR', precision=3,step=10,
                                        description="aspect ratio of the source strip.  "
                                                    "We compute this from the strip's pixel dimensions, "
                                                    "but it can be wrong for media with non-square pixels "
                                                    "(such as DVDs and many other movie formats);  "
                                                    "Blender accepts expressions like 16/9 or 4/3")

    def execute(self, ctx):
        try:
            malfunction, xform, strip_DAR = SequencerLetterboxArbitrary.letterbox_arbitrary_op(ctx.scene, self.align_x, self.align_y, self.strip_DAR)
            if malfunction:
                self.report({'ERROR'}, malfunction)
                return {'CANCELLED'}
            else:
                #self.strip_DAR = strip_DAR
                return {'FINISHED'}
        except BaseException as e:
            self.report({'ERROR'}, e.args[0])
            return {'CANCELLED'}


#
#

def menu_func(self, ctx):
    self.layout.menu(SequencerLetterboxMenu.bl_idname)
    

def register():
    bpy.utils.register_module(__name__)
#    bpy.utils.register_class(SequencerLetterboxMenu)
#    bpy.utils.register_class(SequencerLetterbox)

    bpy.types.SEQUENCER_MT_strip.append(menu_func)

def unregister():
    bpy.types.SEQUENCER_MT_strip.remove(menu_func)
    bpy.utils.unregister_module(__name__)
#    bpy.utils.unregister_class(SequencerLetterbox)
#    bpy.utils.unregister_class(SequencerLetterboxMenu)

if __name__ == "__main__":
    unregister()
    register()
