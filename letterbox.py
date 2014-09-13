bl_info = {
    "name" : "VSE letterboxing",
    "category": "Sequencer",
    "author" : "Robert Forsman <blender@thoth.purplefrog.com>",
    "version": (0,1),
    "blender": (2,7,1),
    "location": "Sequence Editor > Strip",
    "description": "A collection of operators for adding letterboxes to VSE strips that don't have the exact same aspect ratio as the scene.",
}

import bpy


class SequencerLetterboxMenu(bpy.types.Menu):
    bl_idname = "SEQUENCER_MT_strip_letterbox"
    bl_label = "Letterbox"

    def draw(self, ctx):

        layout = self.layout

        # default operator will keep whatever alignment was last used
        layout.operator(SequencerLetterbox.bl_idname, text=SequencerLetterbox.bl_label)

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox Center")
        props.align_x=0.5
        props.align_y=0.5

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox East")
        props.align_x=0
        props.align_y=0.5

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox West")
        props.align_x=1
        props.align_y=0.5

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox North")
        props.align_x=0.5
        props.align_y=0

        props = layout.operator(SequencerLetterbox.bl_idname, text="Letterbox South")
        props.align_x=0.5
        props.align_y=1



class SequencerLetterboxArbitrary:

    @classmethod
    def letterbox_arbitrary_op(cls, scene, align_x=0.5, align_y=0.5):

        xform = SequencerLetterboxArbitrary.letterbox_arbitrary(scene.sequence_editor.active_strip, scene, align_x, align_y)

        for strip in scene.sequence_editor.sequences:
            strip.select = ( strip == xform )
        scene.sequence_editor.active_strip = xform


    @classmethod
    def scene_pixel_aspect(cls, scene):
        return scene.render.pixel_aspect_x / scene.render.pixel_aspect_y

    @classmethod
    def compute_scale(cls, scene, src_strip):
        if hasattr(src_strip, "scene"):
            # this is a Scene strip
            base_width = src_strip.scene.render.resolution_x
            base_height = src_strip.scene.render.resolution_y
        else:
            base_width = src_strip.elements[0].orig_width
            base_height = src_strip.elements[0].orig_height

        if (base_width is None or base_height is None):
            msg = "Unable to determine width&height of base strip.  "
            if (src_strip.type == "IMAGE" or src_strip.type == "MOVIE"):
                msg = msg + "blender was too lazy to parse them from the source media?"
            else:
                msg = msg + "Strip was " + src_strip.type + " instead of IMAGE or MOVIE."
            raise ValueError(msg)

        # this next bit is wrong for DVDs (and CableLabs VoD and anything else with non-square pixels)
        # but blender isn't smart enough to extract it from the source media
        if hasattr(src_strip, "orig_display_aspect_ratio") and 0 != src_strip.orig_display_aspect_ratio:
            source_PAR = src_strip.orig_display_aspect_ratio * base_height / base_width
            source_aspect_ratio = src_strip.orig_display_aspect_ratio
        else:
            if hasattr(src_strip, "scene"):
                source_PAR = cls.scene_pixel_aspect(src_strip.scene)
            elif hasattr(src_strip, "orig_pixel_aspect_ratio") and 0 != src_strip.orig_pixel_aspect_ratio:
                source_PAR = src_strip.orig_pixel_aspect_ratio
            else:
                source_PAR = 1
            source_aspect_ratio = base_width * source_PAR / base_height

        scene_PAR = cls.scene_pixel_aspect(scene)
        scene_aspect_ratio = scene_PAR * scene.render.resolution_x / scene.render.resolution_y
        if scene_aspect_ratio > source_aspect_ratio:
            # wider
            scale_x = source_aspect_ratio / scene_aspect_ratio
            scale_y = 1
        else:
            scale_x = 1
            scale_y = scene_aspect_ratio / source_aspect_ratio
        return scale_x, scale_y

    @classmethod
    def letterbox_arbitrary(cls, strip, scene, align_x=0.5, align_y=0.5):
        if strip is None:
            raise ValueError("You have not selected an action strip to letterbox")

        if (strip.type == 'TRANSFORM'):
            xform = strip
        else :
            # XXX what if the active strip is sound? or something else wrong??
            xform = SequencerLetterboxArbitrary.transform_strip_for(strip, scene)

        src_strip = xform.input_1

        scale_x, scale_y = cls.compute_scale(scene, src_strip)

        xform.scale_start_x = scale_x
        xform.scale_start_y = scale_y

        print(scene.render.resolution_x*(1-scale_x))

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
            print("what is this bullshit? (%s)"%src_strip.use_translation)
            src_strip.use_translation = 0
            print(src_strip.use_translation)

        return xform

    @classmethod
    def transform_strip_for(cls, other_strip, scene):
        for strip in scene.sequence_editor.sequences_all:
            if strip.type == 'TRANSFORM' and strip.input_1 == other_strip:
                return strip
        ch = other_strip.channel+1
        s = strip.frame_start
        e = s + strip.frame_final_duration - 1
        print("%d, %d"%(s,e))
        effect = scene.sequence_editor.sequences.new_effect("Letterbox", 'TRANSFORM', ch, s, frame_end=e,
                                                            seq1=other_strip)
        # because somehow setting frame_end in the previous method call accomplishes nothing
        effect.update()

        return effect


#


class SequencerLetterbox(bpy.types.Operator):
    """an operator which adds or ajusts the transform effect on a strip
    to put letterboxes on the left and right or top and bottom
    to center the content and preserve its original aspect ratio"""
    bl_idname = "sequencer.letterbox_center"
    bl_label = "Letterbox"
    bl_options = {'REGISTER', 'UNDO'}

    align_x = bpy.props.FloatProperty(name="Align X", default=0.5, min=0, max=1.0)
    align_y = bpy.props.FloatProperty(name="Align Y", default=0.5, min=0, max=1.0)

    def execute(self, ctx):
        SequencerLetterboxArbitrary.letterbox_arbitrary_op(ctx.scene, self.align_x, self.align_y)
        return {'FINISHED'}


#
#

def menu_func(self, ctx):
    self.layout.menu(SequencerLetterboxMenu.bl_idname)
    

def register():
    bpy.utils.register_class(SequencerLetterboxMenu)
    bpy.utils.register_class(SequencerLetterbox)

    bpy.types.SEQUENCER_MT_strip.append(menu_func)

def unregister():
    bpy.utils.unregister_class(SequencerLetterbox)
    bpy.utils.unregister_class(SequencerLetterboxMenu)

if __name__ == "__main__":
    register()
