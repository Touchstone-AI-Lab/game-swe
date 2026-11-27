// Copyright (c) 2023 bradson
// This Source Code Form is subject to the terms of the MIT license.
// If a copy of the license was not distributed with this file,
// You can obtain one at https://opensource.org/licenses/MIT/.

using AdaptiveStorage.Fishery;
using AdaptiveStorage.Fishery.Utility.Diagnostics;

namespace AdaptiveStorage.PrintDatas;

[PublicAPI]
public abstract class PrintData : ITransformable.ITransformable
{
	private Vector2 _maxDrawSize = Vector2.positiveInfinity;

	private ShadowData? _shadowData;
	
	public Thing Thing { get; protected set; }

	public Graphic? Graphic { get; protected set; }

	public bool Dirty { get; set; }

	public Vector2 DrawSize { get; protected set; } = Vector2.one;

	public Vector2 RotatedDrawSize => ShouldRotateDrawSize ? DrawSize.Rotated() : DrawSize;

	public Vector2 ScaledDrawSize => DrawSize * DrawScale;

	public Vector2 RotatedScaledDrawSize
		=> ScaledDrawSize is var scaledDrawSize && ShouldRotateDrawSize ? scaledDrawSize.Rotated() : scaledDrawSize;

	protected bool ShouldRotateDrawSize => Graphic is { ShouldDrawRotated: false } && ThingRotation.IsHorizontal;

	protected bool ShouldFlip
		=> Graphic is { ShouldDrawRotated: false } graphic
			&& ThingRotation.AsInt switch
			{
				Rot4.WestInt => graphic.WestFlipped,
				Rot4.EastInt => graphic.EastFlipped,
				_ => false
			};

	[System.Runtime.CompilerServices.CompilerGenerated]
	private Vector2 __DrawScale = Vector2.one;

	public Vector2 DrawScale
	{
		get => __DrawScale;
		set
		{
			if (value == __DrawScale)
				return;

			__DrawScale = value;
			UpdateMatrix();
		}
	}

	public Vector2 RotatedDrawScale => ShouldRotateDrawSize ? DrawScale.Rotated() : DrawScale;

	public Vector2 MaxDrawSize
	{
		get => _maxDrawSize;
		set
		{
			if (value != _maxDrawSize)
				SetDrawScale(DrawScale, value);
		}
	}

	[System.Runtime.CompilerServices.CompilerGenerated]
	private Vector3 __DrawOffset;

	public Vector3 DrawOffset
	{
		get => __DrawOffset;
		set
		{
			__DrawOffset = value;
			UpdateMatrix();
		}
	}

	public RotationAngle RotationAngle
	{
		get => RotationAngle.FromRot4(ThingRotation) + ExtraRotation;
		set
		{
			var rot4 = value.AsRot4;
			ThingRotation = rot4;
			ExtraRotation = (value - rot4).AsFloat;
		}
	}

	[System.Runtime.CompilerServices.CompilerGenerated]
	private Rot4 __ThingRotation = Rot4.Invalid;

	public Rot4 ThingRotation
	{
		get => __ThingRotation;
		set
		{
			if (value == __ThingRotation)
				return;

			__ThingRotation = value;
			SetThingRotation(value);
		}
	}

	[System.Runtime.CompilerServices.CompilerGenerated]
	private float __ExtraRotation;

	public float ExtraRotation
	{
		get => __ExtraRotation;
		set
		{
			if (Mathf.Approximately(value, __ExtraRotation))
				return;

			__ExtraRotation = value;
			UpdateMatrix();
		}
	}

	public TransformData TransformData
	{
		get => new(DrawOffset, DrawScale, RotationAngle);
		set
		{
			DrawOffset = value.Position;
			DrawScale = value.Scale;
			RotationAngle = value.CombinedRotation;
		}
	}

	public ShadowData? ShadowData
	{
		get => _shadowData is var shadowData && shadowData != _defaultShadowData ? shadowData : null;
		private set => _shadowData = value;
	}

	public bool DrawShadow
	{
		get => _shadowData != null;
		set
			=> _shadowData = value
				? (_shadowData == _defaultShadowData ? Graphic?.ShadowGraphic?.shadowInfo : null) ?? _defaultShadowData
				: null;
	}

	public virtual bool ShouldPrint => Thing.def.drawerType is DrawerType.MapMeshOnly or DrawerType.MapMeshAndRealTime;

	public virtual bool ShouldDraw => Thing.def.drawerType is DrawerType.RealtimeOnly or DrawerType.MapMeshAndRealTime;

	public void PrintAt(SectionLayer layer, in Vector3 drawLoc) => PrintAt(layer, new TransformData(drawLoc));

	public abstract void PrintAt(SectionLayer layer, in TransformData transformData);

	public void DrawAt(in Vector3 drawLoc) => DrawAt(new TransformData(drawLoc));

	public abstract void DrawAt(in TransformData transformData);

#if !V1_4
	public virtual void DynamicDrawPhaseAt(DrawPhase phase, in TransformData transformData)
	{
		if (phase == DrawPhase.Draw)
			DrawAt(transformData);
	}
#endif

	public virtual void NotifyMaterialPossiblyChanged()
	{
		var newDrawSize = Graphic?.drawSize ?? Vector2.one;
		if (newDrawSize == DrawSize)
			return;

		DrawSize = newDrawSize;
		SetDrawScale(DrawScale, MaxDrawSize);
	}

	protected virtual void UpdateMatrix()
	{
	}

	public void SetDrawScale(Vector2 drawScale, Vector2 maxDrawSize)
	{
		if (maxDrawSize == MaxDrawSize && drawScale == DrawScale)
			return;
		
		_maxDrawSize = maxDrawSize;
		
		var meshSize = DrawSize;
		var scaledSize = meshSize * drawScale;

		if (scaledSize.x > maxDrawSize.x)
			scaledSize *= maxDrawSize.x / scaledSize.x;

		if (scaledSize.y > maxDrawSize.y)
			scaledSize *= maxDrawSize.y / scaledSize.y;

		DrawScale = scaledSize / meshSize;
	}

	public virtual void SetThingRotation(Rot4 thingRotation)
	{
	}

	public override string ToString() => $"{base.ToString()} (Thing: '{Thing}', Graphic: '{Graphic}')";

	private static readonly ShadowData _defaultShadowData = new();
	
	public static PrintData Create(Thing thing, Graphic? graphic, bool ignoreThingType = false)
	{
		Guard.IsNotNull(thing);

		var result = Factories
				.Find((thing, graphic),
					ignoreThingType
						? static (c, factory) => factory.IsCompatibleWith(c.thing, c.graphic, true)
						: static (c, factory) => factory.IsCompatibleWith(c.thing, c.graphic, false))
				?.CreateFor(thing, graphic)
			?? (ignoreThingType ? new UnsupportedGraphicPrintData() : new UnsupportedThingPrintData());

		result.Thing = thing;
		result.Graphic = graphic;
		result.DrawSize = graphic?.drawSize ?? Vector2.one;
		result.ShadowData = graphic?.ShadowGraphic?.shadowInfo ?? _defaultShadowData;
		result.ThingRotation = Rot4.North;

		return result;
	}

#pragma warning disable CS8618
	protected PrintData()
#pragma warning restore CS8618
	{
	}

	public static List<Factory> Factories { get; } =
	[
		new OptimizedPrintData.Factory(),
		new ITransformableGraphicPrintData.Factory(),
		new ITransformableThingPrintData.Factory(),
		new MinifiedThingPrintData.Factory(),
		new CorpsePrintData.Factory(),
		new UnsupportedGraphicPrintData.Factory(),
		new UnsupportedThingPrintData.Factory()
	];

	public abstract class Factory
	{
		public abstract bool IsCompatibleWith(Thing thing, Graphic? graphic, bool ignoreThingType);
		
		public abstract PrintData CreateFor(Thing thing, Graphic? graphic);
	}
}
